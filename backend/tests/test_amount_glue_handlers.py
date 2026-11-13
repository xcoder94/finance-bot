"""Quick-entry text: separate numbers are never glued into one amount."""

from types import SimpleNamespace

import pytest

from app.parsing.stub import StubParser
from app.parsing.types import ParseResponse, ParsedOperation
from bot.quick_entry.handlers import handle_quick_entry_text, set_parser_override

from tests.test_phase16_prefilter_handlers import (
    FailingParser,
    SessionFactory,
    create_user,
    make_message,
    pytestmark,  # noqa: F401  (skip without db + anyio)
    reset_parser_override,  # noqa: F401  (autouse fixture)
    rollback_session,
    seed_taxi_setup,
)


def _model_answer(amount: int) -> ParseResponse:
    return ParseResponse(
        operations=[
            ParsedOperation(
                type="expense",
                amount=amount,
                currency="UZS",
                wallet_hint=None,
                category="Такси",
                comment=None,
            )
        ]
    )


# (text, amount shown in the card, True = answered by the fast path (model not called))
CASES = [
    # the bug: separate numbers must go to the model, which returns the real amount
    ("такси 20000 2 раза", 20_000, False),
    ("такси 2 20000", 20_000, False),
    ("такси 12 15000", 15_000, False),
    ("taksi 20000 2 marta", 20_000, False),
    ("taksi 2 marta 20000", 20_000, False),
    # real thousands grouping stays on the fast path
    ("такси 20 000", 20_000, True),
    ("такси 1 215 000", 1_215_000, True),
    ("такси 20_000", 20_000, True),
    ("такси 20к", 20_000, True),
    ("такси 20 тыс", 20_000, True),
    ("такси 20 000 сум", 20_000, True),
    ("такси 20000 сум", 20_000, True),
    ("taksi 20 ming", 20_000, True),
    ("такси 1 215 000 сум", 1_215_000, True),
    # multiplier glued to a word or sign: not a sum, but one more number -> model
    ("такси 20000 x2", 40_000, False),
    ("такси 20000 х2", 40_000, False),
    ("такси 20000x2", 40_000, False),
    ("такси 20000 *2", 40_000, False),
    ("такси 15000 x3", 45_000, False),
    ("такси 15 000 х3", 45_000, False),
    ("такси 2х20000", 40_000, False),
    # glued digits that are part of a name stay on the fast path
    ("такси express24 55000", 55_000, False),
    # wrong underscore grouping is never guessed
    ("такси 20__000", 20_000, False),
    ("такси 2_0000", 20_000, False),
    ("такси 20 _000", 20_000, False),
    ("такси 20_000_", 20_000, False),
    # whitelist: digits glued to words/signs, signs, tab -> model
    ("такси 2по20000", 20_000, False),
    ("такси 2шт20000", 20_000, False),
    ("taksi 2ta20000", 20_000, False),
    ("такси 20000 Ｘ2", 40_000, False),
    ("такси 20000 ҳ2", 40_000, False),
    ("такси 20к2", 20_000, False),
    ("такси 3x", 3, False),
    ("такси −20000", 20_000, False),
    ("такси 4\t661", 4_661, False),
    ("такси 20000раз2", 20_000, False),
    ("такси 20000 2 раза", 20_000, False),
    ("такси 20 000,50", 20_000, False),
    ("такси 1.5 млн", 1_500_000, False),
    # fast path controls
    ("такси 20000.", 20_000, True),
    ("такси (20000)", 20_000, True),
    ("такси 20 000,", 20_000, True),
    ("такси 20\u2009000", 20_000, True),
]


def _fmt(n: int) -> str:
    return f"{n:,}".replace(",", " ")


@pytest.mark.parametrize("text,amount,fast", CASES)
async def test_amount_not_glued(
    text: str, amount: int, fast: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with rollback_session() as session:
        user, budget = await create_user(session, telegram_id=9_177_001)
        await seed_taxi_setup(session, user, budget)
        set_parser_override(
            FailingParser()
            if fast
            else StubParser(responses={text: _model_answer(amount)})
        )
        monkeypatch.setattr(
            "bot.quick_entry.handlers.async_session_factory", SessionFactory(session)
        )
        message = make_message(telegram_id=user.telegram_id, text=text)
        await handle_quick_entry_text(message, SimpleNamespace())

        message.answer.assert_awaited_once()
        card = message.answer.await_args.args[0]
        assert f"{_fmt(amount)} сум" in card
        assert budget.daily_model_calls == (0 if fast else 1)
