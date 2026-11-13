"""'$ 20' equals '$20'; every spelling of the sum word is the UZS currency, spaced or glued."""

from types import SimpleNamespace

import pytest

from app.parsing.prefilter import PrefilterCategory, try_prefilter
from app.parsing.stub import StubParser
from app.parsing.types import ParseResponse, ParsedOperation
from bot.quick_entry.handlers import handle_quick_entry_text, set_parser_override

from tests.test_phase16_prefilter_handlers import (
    FailingParser,
    SessionFactory,
    create_user,
    make_message,
    pytestmark,  # noqa: F401
    reset_parser_override,  # noqa: F401
    rollback_session,
    seed_taxi_setup,
)

_CATS = [
    PrefilterCategory(id=1, name="Такси", translation_key=None, parent_id=None),
    PrefilterCategory(id=2, name="Taksi", translation_key=None, parent_id=None),
    PrefilterCategory(id=4, name="Кофе", translation_key=None, parent_id=None),
]

SUM_WORDS = ["so'm", "so‘m", "so`m", "soʻm", "so’m", "soʼm", "сўм", "sum", "сум", "UZS", "SO'M", "Сўм"]


def _run(text: str):
    return try_prefilter(
        text, wallet_names=[], expense_categories=_CATS, income_categories=[], seed_name_by_key={}
    ).operation


@pytest.mark.parametrize("word", SUM_WORDS)
@pytest.mark.parametrize("sep", [" ", ""])
@pytest.mark.parametrize("cat", ["такси", "taksi"])
def test_sum_word_is_currency_not_comment(cat: str, sep: str, word: str) -> None:
    for number in ("20000", "20 000"):
        op = _run(f"{cat} {number}{sep}{word}")
        assert op is not None, (cat, number, sep, word)
        assert (op.amount, op.currency, op.comment) == (20_000, "UZS", None), (cat, sep, word)


def test_sum_word_before_comment_text() -> None:
    op = _run("taksi 20000 so'm ofisga")
    assert (op.amount, op.currency, op.comment) == (20_000, "UZS", "ofisga")


@pytest.mark.parametrize(
    "text",
    ["такси 20000 so'm2", "такси 20000so'm2", "такси 20000 sum 2", "такси 20000-so'm"],
)
def test_sum_word_with_other_digits_or_glue_goes_to_model(text: str) -> None:
    assert _run(text) is None, text


@pytest.mark.parametrize("text", ["кофе $ 20", "$ 20 кофе", "кофе $ 20", "кофе $ 20 000"])
def test_dollar_space_equals_dollar_glued(text: str) -> None:
    op = _run(text)
    assert op is not None, text
    assert op.currency == "USD" and op.comment is None, (text, op)
    assert op.amount == (20_000 if text.endswith("000") else 20)


def test_dollar_space_with_second_mark_still_model() -> None:
    assert _run("кофе $ 20 usd") is None
    assert _run("кофе $ 20 тыс") is None
    assert _run("кофе $ 20 k") is None
    assert _run("кофе $ 2 млн") is None
    op = _run("кофе $   20")
    assert (op.amount, op.currency, op.comment) == (20, "USD", None)


def _answer() -> ParseResponse:
    return ParseResponse(
        operations=[
            ParsedOperation(
                type="expense", amount=20_000, currency="UZS", wallet_hint=None,
                category="Такси", comment=None,
            )
        ]
    )


H_CASES = [
    ("такси 20000 so'm", "20 000 сум"),
    ("такси 20000 сўм", "20 000 сум"),
    ("такси 20000 so‘m", "20 000 сум"),
    ("taksi 20000 sum", "20 000 сум"),
    ("такси 20000so'm", "20 000 сум"),
    ("такси 20000сўм", "20 000 сум"),
    ("такси $ 20", "Кошелька в долларах"),
    ("такси $20", "Кошелька в долларах"),
]


@pytest.mark.parametrize("text,shown", H_CASES)
async def test_handler_fast_path(text: str, shown: str, monkeypatch: pytest.MonkeyPatch) -> None:
    async with rollback_session() as session:
        user, budget = await create_user(session, telegram_id=9_177_011)
        await seed_taxi_setup(session, user, budget)
        set_parser_override(FailingParser())
        monkeypatch.setattr(
            "bot.quick_entry.handlers.async_session_factory", SessionFactory(session)
        )
        message = make_message(telegram_id=user.telegram_id, text=text)
        await handle_quick_entry_text(message, SimpleNamespace())
        message.answer.assert_awaited_once()
        card = message.answer.await_args.args[0]
        assert shown in card, card
        for word in ("so'm", "so‘m", "сўм", "sum", "$"):
            assert word not in card.replace("Кошелька в долларах", ""), card
        assert budget.daily_model_calls == 0
