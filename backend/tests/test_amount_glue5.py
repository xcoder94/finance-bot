"""Suffix word takes letters only; dash glued to a word, $ before the number and emoji stay fast."""

import random
import re
from types import SimpleNamespace

import pytest

from app.parsing.prefilter import PrefilterCategory, _find_amounts, try_prefilter
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
    PrefilterCategory(id=3, name="Обед", translation_key=None, parent_id=None),
    PrefilterCategory(id=4, name="Кофе", translation_key=None, parent_id=None),
]


def _run(text: str):
    return try_prefilter(
        text, wallet_names=[], expense_categories=_CATS, income_categories=[], seed_name_by_key={}
    ).operation


# bug A: digits after the suffix word are not part of it
@pytest.mark.parametrize(
    "text",
    [
        "taksi 20 ming25000",
        "taksi 20 ming2 marta",
        "такси 20 ming2 тыс",
        "такси 20 мингx2",
        "taksi 20 ming_5",
        "продукты 613 мингп1420000тыс",
        "taksi 20 mingta2",
        "такси 20 мингта5",
    ],
)
def test_digit_after_suffix_word_goes_to_model(text: str) -> None:
    assert _run(text) is None


def test_suffix_word_with_letters_still_fast() -> None:
    assert _run("taksi 20 ming").amount == 20_000
    assert _run("taksi 20 mingta").amount == 20_000
    assert _run("такси 20 минг").amount == 20_000


# bug B: (text, amount, currency, comment) must be fast and clean
FAST = [
    ("такси-20000", 20_000, None, None),
    ("Такси-20000", 20_000, None, None),
    ("обед-45000", 45_000, None, None),
    ("taksi-20000", 20_000, None, None),
    ("такси–20000", 20_000, None, None),
    ("такси—20000", 20_000, None, None),
    ("такси-200 тыс", 200_000, None, None),
    ("такси-20 ming", 20_000, None, None),
    ("такси-20 000", 20_000, None, None),
    ("$20 такси", 20, "USD", None),
    ("такси $20", 20, "USD", None),
    ("кофе $20", 20, "USD", None),
    ("такси 20000сум", 20_000, "UZS", None),
    ("такси☕20000", 20_000, None, "☕"),
    ("такси 20000☕", 20_000, None, "☕"),
    ("🚕20000 такси", 20_000, None, "🚕"),
    ("такси 20000 🚕", 20_000, None, "🚕"),
    ("такси 20 тыс💰", 20_000, None, "💰"),
]


@pytest.mark.parametrize("text,amount,currency,comment", FAST)
def test_prefilter_fast(text: str, amount: int, currency: str | None, comment: str | None) -> None:
    op = _run(text)
    assert op is not None, text
    assert (op.amount, op.currency, op.comment) == (amount, currency, comment)


@pytest.mark.parametrize(
    "text",
    [
        "такси -20000",
        "такси −20000",
        "такси−20000",
        "−20000 такси",
        "-20000 такси",
        "такси 5-20000",
        "такси 20000-",
        "такси-20000-",
        "такси $20 usd",
        "такси $20 тыс",
        "такси $20к",
        "такси $20 млн",
        "такси €20",
        "такси$20",
        "такси ✖20000",
        "такси ✕20000",
        "такси ❌20000",
        "такси 20000✖",
        "такси 20000❌2",
        "такси ☕2 20000",
        "такси 2️⃣0000",
        "такси 20000☕2",
        "такси 20000☕ x2",
        "такси 20000x☕2",
        "такси 20000so'm",
        "такси 20000сўм",
    ],
)
def test_prefilter_still_model(text: str) -> None:
    assert _run(text) is None, text


# property: I1-I3 for the new forms
_AROUND = ["", "-", "–", "—", "‐", "‑", "−", " -", " −", "☕", "🚕", "❤️", "❌", "✖", " $", " €", " "]


def _assert_covered(text: str) -> None:
    found = _find_amounts(text)
    assert len(found) == 1, text
    start, end = found[0].span
    for m in re.finditer(r"\d", text):
        assert start <= m.start() < end, text


def test_random_neighbours_i1_i3() -> None:
    rnd = random.Random(21)
    bad: list[str] = []
    ok_before = {" ", "-", "–", "—", "‐", "‑", "☕", "🚕", "❤️", " $"}
    for _ in range(8_000):
        n = rnd.randint(1, 10 ** rnd.randint(1, 8))
        word = rnd.choice(["такси", "taksi", "Такси", "такси 2 раза"])
        before, after = rnd.choice(_AROUND), rnd.choice(["", " ", "☕", "🚕", "-", "−", "x", "$", "_2", "✖"])
        text = f"{word}{before}{n}{after}"
        op = _run(text)
        expect = (
            word != "такси 2 раза"
            and before in ok_before
            and before != ""  # number glued to the word is never an amount
            and after in {"", " ", "☕", "🚕", "$"}
            and not (before == " $" and after == "$")
        )
        if expect != (op is not None):
            bad.append(text)
            continue
        if op is not None:
            _assert_covered(text)
    assert not bad, bad[:10]


def test_random_suffix_digit_never_fast() -> None:
    rnd = random.Random(33)
    bad: list[str] = []
    for _ in range(5_000):
        suf = rnd.choice(["ming", "минг", "mingta", "мингп", "MING", "Минг"])
        tail = rnd.choice(list("0123456789") + ["٣", "２", "_5", "_٣"])
        text = f"{rnd.choice(['taksi', 'такси'])} {rnd.randint(1, 999)}{rnd.choice(['', ' '])}{suf}{tail}{rnd.choice(['', 'x', ' тыс', '000', ' 2'])}"
        if _run(text) is not None:
            bad.append(text)
    assert not bad, bad[:10]


# through the handler: amount, currency, card text
def _answer(amount: int) -> ParseResponse:
    return ParseResponse(
        operations=[
            ParsedOperation(
                type="expense", amount=amount, currency="UZS", wallet_hint=None,
                category="Такси", comment=None,
            )
        ]
    )


H_CASES = [
    ("такси-20000", "20 000 сум", True),
    ("taksi-20000", "20 000 сум", True),
    ("такси-200 тыс", "200 000 сум", True),
    ("такси 20000сум", "20 000 сум", True),
    ("такси☕20000", "20 000 сум", True),
    ("такси 20000🚕", "20 000 сум", True),
    ("такси $20", "Кошелька в долларах", True),
    ("taksi 20 ming25000", "20 000 сум", False),
    ("такси 20 ming2 тыс", "20 000 сум", False),
    ("продукты 613 мингп1420000тыс", "20 000 сум", False),
    ("такси -20000", "20 000 сум", False),
    ("такси −20000", "20 000 сум", False),
]


@pytest.mark.parametrize("text,shown,fast", H_CASES)
async def test_handler(text: str, shown: str, fast: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    async with rollback_session() as session:
        user, budget = await create_user(session, telegram_id=9_177_005)
        await seed_taxi_setup(session, user, budget)
        set_parser_override(
            FailingParser() if fast else StubParser(responses={text: _answer(20_000)})
        )
        monkeypatch.setattr(
            "bot.quick_entry.handlers.async_session_factory", SessionFactory(session)
        )
        message = make_message(telegram_id=user.telegram_id, text=text)
        await handle_quick_entry_text(message, SimpleNamespace())
        message.answer.assert_awaited_once()
        card = message.answer.await_args.args[0]
        assert shown in card, card
        assert budget.daily_model_calls == (0 if fast else 1)
