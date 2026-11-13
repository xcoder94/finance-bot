"""Model prompt carries one unambiguous multiplier / count / two-numbers rule.

The real model is NOT exercised here: only the prompt text and the parsing (through the
quick-entry handler) of the answers that rule asks for.
"""

from types import SimpleNamespace

import pytest

from app.parsing.http_adapter import _parse_response_payload
from app.parsing.prompt import IMMUTABLE_PARSER_INSTRUCTIONS as PROMPT
from app.parsing.stub import StubParser
from app.parsing.types import ParseResponse, ParsedOperation
from bot.quick_entry.handlers import handle_quick_entry_text, set_parser_override

from tests.test_phase16_prefilter_handlers import (
    SessionFactory,
    create_user,
    make_message,
    pytestmark,  # noqa: F401  (skip without db + anyio)
    reset_parser_override,  # noqa: F401  (autouse fixture)
    rollback_session,
    seed_taxi_setup,
)


def _rule() -> str:
    start = PROMPT.index("- Multipliers, counts")
    return PROMPT[start : PROMPT.index("\n", start)]


def test_prompt_rule_covers_every_multiplier_shape() -> None:
    rule = _rule()
    for marker in ("20000 x2", "x2 20000", "2 x 20000", "3 шт по 15000", "2 раза по 20000", "2 ta 15000 dan"):
        assert marker in rule
    assert "any order and case" in rule
    assert "2 × 20000" in rule
    assert "20000 2 раза" in rule and "2 чел 45000" in rule
    assert "12 15000" in rule and "NOT type ambiguous" in rule and "NOT two operations" in rule


def test_prompt_has_no_dangling_ambiguity_reference() -> None:
    assert "ambiguity rules above" not in PROMPT
    assert "choose by the ambiguity" not in PROMPT


def _answer(amount: int, comment: str) -> ParseResponse:
    return ParseResponse(
        operations=[
            ParsedOperation(
                type="expense", amount=amount, currency="UZS", wallet_hint=None,
                category="Такси", comment=comment,
            )
        ]
    )


# model answers the prompt asks for: (text, answer the model gives, amount shown in the card)
CASES = [
    ("такси 20000 x2", _answer(40000, "2 × 20000"), 40_000),
    ("такси x2 20000", _answer(40000, "2 × 20000"), 40_000),
    ("такси 3 шт по 15000", _answer(45000, "3 × 15000"), 45_000),
    ("такси 20000 2 раза", _answer(20000, "2 раза"), 20_000),
    ("такси 2 чел 45000", _answer(45000, "2 чел"), 45_000),
    ("такси 12 15000", _answer(15000, "12"), 15_000),
]


@pytest.mark.parametrize("text,answer,amount", CASES)
async def test_model_answer_for_each_rule_case_is_one_row(
    text: str, answer: ParseResponse, amount: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with rollback_session() as session:
        user, budget = await create_user(session, telegram_id=9_177_050)
        await seed_taxi_setup(session, user, budget)
        set_parser_override(StubParser(responses={text: answer}))
        monkeypatch.setattr("bot.quick_entry.handlers.async_session_factory", SessionFactory(session))
        message = make_message(telegram_id=user.telegram_id, text=text)
        await handle_quick_entry_text(message, SimpleNamespace())
        message.answer.assert_awaited_once()
        card = message.answer.await_args.args[0]
        assert f"{amount:,}".replace(",", " ") + " сум" in card
        assert budget.daily_model_calls == 1


def test_single_operation_answer_parses_through_adapter() -> None:
    resp = _parse_response_payload(
        {"operations": [{"type": "expense", "amount": 40000, "currency": "UZS", "category": "Такси", "comment": "2 × 20000"}]}
    )
    assert len(resp.operations) == 1 and resp.operations[0].amount == 40000
