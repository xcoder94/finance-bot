"""ux-r4: Latin/Cyrillic dollar words give USD; card currency follows the chosen wallet."""

import pytest

from app.parsing.prefilter import try_prefilter
from tests.test_phase16_prefilter import _expense


@pytest.mark.parametrize(
    ("text", "currency"),
    [
        ("taksi 50 dollar", "USD"),
        ("taksi 50 dollarga", "USD"),
        ("taksi 50 Dollar", "USD"),
        ("taksi 50 usd", "USD"),
        ("taksi 50$", "USD"),
        ("такси 50 доллары", "USD"),
        ("такси 50 долларов", "USD"),
        ("taksi 50 so'm", "UZS"),
        ("taksi 50000", None),
    ],
)
def test_currency_word(text, currency) -> None:
    result = try_prefilter(
        text,
        wallet_names=[],
        expense_categories=[_expense("Такси", translation_key="taxi")],
        income_categories=[],
    )
    assert result.operation is not None, result.reason
    assert result.operation.currency == currency
    assert result.operation.amount == 50 or currency is None
    assert "dollar" not in (result.operation.comment or "").casefold()


# ------------------------------------------------------------------ card currency (bot)

from types import SimpleNamespace  # noqa: E402

from app.models.transaction import Transaction  # noqa: E402
from bot.quick_entry.handlers import handle_quick_entry_text, set_parser_override  # noqa: E402
from sqlalchemy import select  # noqa: E402
from tests.test_phase16_prefilter_handlers import (  # noqa: E402
    SessionFactory,
    create_user,
    make_message,
    make_wallet,
    pytestmark,  # noqa: F401
    rollback_session,
    seed_taxi_setup,
)


async def _run(monkeypatch, tg, text):
    async with rollback_session() as session:
        user, budget = await create_user(session, telegram_id=tg)
        uzs, _ = await seed_taxi_setup(session, user, budget)
        usd = make_wallet(budget, name="Карта USD", currency="USD")
        session.add(usd)
        await session.flush()
        set_parser_override(None)
        monkeypatch.setattr("bot.quick_entry.handlers.async_session_factory", SessionFactory(session))
        message = make_message(telegram_id=tg, text=text)
        await handle_quick_entry_text(message, SimpleNamespace())
        txns = list(await session.scalars(select(Transaction).where(Transaction.family_budget_id == budget.id)))
        return message.answer.await_args.args[0], txns, uzs, usd


async def test_latin_dollar_books_into_usd_wallet_and_card_says_usd(monkeypatch) -> None:
    card, txns, _uzs, usd = await _run(monkeypatch, 9_730_001, "taksi 50 dollar")
    assert len(txns) == 1 and txns[0].wallet_id == usd.id and txns[0].amount == 50
    assert "USD" in card and "сум" not in card.split("Баланс")[0]


async def test_hinted_usd_wallet_without_currency_word_card_matches_wallet(monkeypatch) -> None:
    card, txns, _uzs, usd = await _run(monkeypatch, 9_730_011, "такси 50000 с Карта USD")
    assert len(txns) == 1 and txns[0].wallet_id == usd.id
    assert "USD" in card and "50 000 сум" not in card
