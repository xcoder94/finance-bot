"""ux-next7 (NEW-3): every form of the sum word is a currency, like the dollar words.

Through the bot handler with a USD default wallet: the saved entry has the amount and UZS."""

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.transaction import Transaction
from app.parsing.prefilter import try_prefilter
from bot.quick_entry.handlers import handle_quick_entry_text, set_parser_override
from tests.test_phase16_prefilter import _expense
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

SUM_FORMS = [
    "som", "soum", "so'm", "so‘m", "so’m", "soʻm", "soʼm", "so`m", "SO'M", "Som",
    "sum", "сум", "Сум", "сўм", "сум",
    "so'mga", "so'mlik", "so'mdan", "so'mda", "somga", "somlik", "soumga", "sumga", "sumlik",
    "сумов", "сума", "сумах", "сумы", "сумам", "сўмга", "сўмлик", "сумга", "сумлик",
]
NOT_CURRENCY = ["сумка", "сумма", "summa", "some", "sumka", "somsa", "суммы", "сумочка", "summary"]


async def _run(monkeypatch, tg, text):
    async with rollback_session() as session:
        user, budget = await create_user(session, telegram_id=tg)
        uzs, _ = await seed_taxi_setup(session, user, budget)
        usd = make_wallet(budget, name="Карта USD", currency="USD")
        session.add(usd)
        await session.flush()
        user.default_wallet_id = usd.id
        await session.flush()
        set_parser_override(FailingParser())
        monkeypatch.setattr("bot.quick_entry.handlers.async_session_factory", SessionFactory(session))
        message = make_message(telegram_id=tg, text=text)
        await handle_quick_entry_text(message, SimpleNamespace())
        txns = list(await session.scalars(select(Transaction).where(Transaction.family_budget_id == budget.id)))
        return txns, uzs, usd


@pytest.mark.parametrize("form", SUM_FORMS)
async def test_sum_form_saved_as_uzs(monkeypatch, form) -> None:
    txns, uzs, _usd = await _run(monkeypatch, 9_770_001, f"taksi 20000 {form}")
    assert len(txns) == 1 and txns[0].wallet_id == uzs.id and txns[0].amount == 20000


@pytest.mark.parametrize(
    "text",
    ["taksi 20 mingso'm", "taksi 20 ming so'mga", "такси 20 ксум", "такси 20 тысяч сумов", "taksi 20 mingsom",
     "taksi 20kso'm", "taksi 20 mlnsum"],
)
async def test_glued_magnitude_and_sum_word(monkeypatch, text) -> None:
    txns, uzs, usd = await _run(monkeypatch, 9_770_002, text)
    # either saved correctly as UZS or sent to the model (FailingParser: nothing saved); never USD
    assert all(t.wallet_id == uzs.id for t in txns)
    assert len(txns) == 1, "must be taken on the fast path with the right amount"
    assert txns[0].amount in (20_000, 20_000_000)


@pytest.mark.parametrize("word", NOT_CURRENCY)
def test_neighbours_are_not_currency(word) -> None:
    result = try_prefilter(
        f"taksi 20000 {word}",
        wallet_names=[],
        expense_categories=[_expense("Такси", translation_key="taxi")],
        income_categories=[],
    )
    assert result.operation is not None
    assert result.operation.currency is None


@pytest.mark.parametrize("form", SUM_FORMS)
def test_sum_form_left_of_number(form) -> None:
    result = try_prefilter(
        f"taksi {form} 20000",
        wallet_names=[],
        expense_categories=[_expense("Такси", translation_key="taxi")],
        income_categories=[],
    )
    # a sum word before the number is not the amount's mark: model, never a silent bare amount
    assert result.operation is None or result.operation.currency == "UZS"
