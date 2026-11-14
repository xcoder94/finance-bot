"""ux-next6 M1/L1: a currency mark next to the amount is never lost on the fast path."""

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.transaction import Transaction
from app.models.wallet import Wallet
from app.parsing import prefilter as P
from app.parsing.stub import StubParser
from app.parsing.types import ParseResponse, ParsedOperation
from bot.quick_entry.handlers import handle_quick_entry_text, set_parser_override

from tests.test_phase16_prefilter_handlers import (
    FailingParser,
    SessionFactory,
    create_user,
    make_message,
    make_wallet,
    pytestmark,  # noqa: F401
    reset_parser_override,  # noqa: F401
    rollback_session,
    seed_taxi_setup,
)

CATS = [
    P.PrefilterCategory(id=i, name=n, translation_key=None, parent_id=None)
    for i, n in enumerate(["Такси", "Продукты", "Кафе", "Зарплата"])
]
SUM_WORDS = ["so'm", "so‘m", "сўм", "сум", "sum", "uzs"]
USD_WORDS = ["$", "usd", "доллар", "dollar"]
MAGS = ["ming", "минг", "тыс", "тыс.", "тысяч", "k", "к", "mln", "млн", "million", "миллион"]
FACTOR = {"ming": 1000, "минг": 1000, "тыс": 1000, "тыс.": 1000, "тысяч": 1000, "k": 1000,
          "к": 1000, "mln": 10**6, "млн": 10**6, "million": 10**6, "миллион": 10**6}


def _run(text: str):
    return P.try_prefilter(
        text, wallet_names=["Карта", "Наличные"], expense_categories=CATS[:3],
        income_categories=CATS[3:], seed_name_by_key={},
    )


def _combos():
    for mag in MAGS:
        for cur in SUM_WORDS + USD_WORDS:
            for sep in (" ", ""):
                yield f"такси 20{sep}{mag} {cur}", 20 * FACTOR[mag], ("UZS" if cur in SUM_WORDS else "USD")


def test_magnitude_then_currency_never_loses_currency() -> None:
    lost = []
    for text, amount, cur in _combos():
        op = _run(text).operation
        if op is not None and (op.amount != amount or op.currency != cur):
            lost.append((text, op.amount, op.currency))
    assert not lost, f"{len(lost)} lost, e.g. {lost[:5]}"


HANDLER_CASES = [
    ("такси 20 тыс $", 20_000, "USD", "UZS"),
    ("такси 20 тыс usd", 20_000, "USD", "UZS"),
    ("такси 20 минг доллар", 20_000, "USD", "UZS"),
    ("такси 20 ming so'm", 20_000, "UZS", "USD"),
    ("такси 20 mln so'm", 20_000_000, "UZS", "USD"),
    ("такси 20 тыс. сум", 20_000, "UZS", "USD"),
]


@pytest.mark.parametrize("text,amount,cur,default_cur", HANDLER_CASES)
async def test_saved_record_has_amount_and_currency(
    text: str, amount: int, cur: str, default_cur: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with rollback_session() as session:
        user, budget = await create_user(session, telegram_id=9_177_601)
        wallet, _ = await seed_taxi_setup(session, user, budget)
        usd = make_wallet(budget, name="Долларовый", currency="USD")
        session.add(usd)
        await session.flush()
        user.default_wallet_id = (usd if default_cur == "USD" else wallet).id
        await session.flush()
        set_parser_override(
            StubParser(responses={text: ParseResponse(operations=[ParsedOperation(
                type="expense", amount=amount, currency=cur, wallet_hint=None,
                category="Такси", comment=None)])})
        )
        monkeypatch.setattr(
            "bot.quick_entry.handlers.async_session_factory", SessionFactory(session)
        )
        message = make_message(telegram_id=user.telegram_id, text=text)
        await handle_quick_entry_text(message, SimpleNamespace())
        tx = (await session.scalars(
            select(Transaction).where(Transaction.family_budget_id == budget.id)
        )).one()
        w = await session.get(Wallet, tx.wallet_id)
        assert (tx.amount, w.currency) == (amount, cur)


FAST_CASES = [
    ("такси 20 тыс сум", 20_000, "UZS", "UZS"),
    ("такси 20 тыс $", 20_000, "USD", "UZS"),
    ("taksi 20 ming so'm", 20_000, "UZS", "UZS"),
    ("taksi 20 ming so'm", 20_000, "UZS", "USD"),
    ("такси 20к сум", 20_000, "UZS", "UZS"),
    ("такси 2 млн сум", 2_000_000, "UZS", "UZS"),
    ("такси 20 mln so'm", 20_000_000, "UZS", "USD"),
    ("такси 20 минг доллар", 20_000, "USD", "UZS"),
]


@pytest.mark.parametrize("text,amount,cur,default_cur", FAST_CASES)
async def test_magnitude_plus_currency_is_taken_on_fast_path(
    text: str, amount: int, cur: str, default_cur: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with rollback_session() as session:
        user, budget = await create_user(session, telegram_id=9_177_602)
        wallet, _ = await seed_taxi_setup(session, user, budget)
        usd = make_wallet(budget, name="Долларовый", currency="USD")
        session.add(usd)
        await session.flush()
        user.default_wallet_id = (usd if default_cur == "USD" else wallet).id
        await session.flush()
        set_parser_override(FailingParser())
        monkeypatch.setattr(
            "bot.quick_entry.handlers.async_session_factory", SessionFactory(session)
        )
        message = make_message(telegram_id=user.telegram_id, text=text)
        await handle_quick_entry_text(message, SimpleNamespace())
        tx = (await session.scalars(
            select(Transaction).where(Transaction.family_budget_id == budget.id)
        )).one()
        w = await session.get(Wallet, tx.wallet_id)
        assert (tx.amount, w.currency) == (amount, cur)
        assert budget.daily_model_calls == 0


def test_two_currencies_or_unknown_between_go_to_model() -> None:
    for text in ["такси 20 тыс сум $", "такси 20 тыс $ usd", "такси 20 тыс бы сум", "такси 20 тыс сум!$"]:
        assert _run(text).operation is None, text


def test_table_is_fast_with_right_currency_where_not_a_preposition() -> None:
    slow = []
    for text, amount, cur in _combos():
        spaced_k = " к " in text or " k " in text
        if spaced_k and not text.endswith("$"):
            continue  # "20 к сум" is the preposition rule: model
        op = _run(text).operation
        if op is None or (op.amount, op.currency) != (amount, cur):
            slow.append(text)
    assert not slow, slow[:8]
