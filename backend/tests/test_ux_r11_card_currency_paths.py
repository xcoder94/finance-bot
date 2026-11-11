"""ux-r11: the bot card shows the chosen wallet's currency in the 'waiting for type' and photo paths."""

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.transaction import Transaction
from app.parsing.types import ParsedOperation, ParseResponse
from bot.quick_entry.handlers import handle_quick_entry_text, set_parser_override
from bot.quick_entry.receipt_photo import handle_receipt_photo, set_receipt_parser_override
from tests import test_phase15_receipt_photo as photo
from tests.test_quick_entry_flow import (  # noqa: F401
    SessionFactory,
    StubParser,
    create_user,
    make_message,
    make_wallet,
    pytestmark,
    rollback_session,
)


@pytest.fixture(autouse=True)
def _reset_parsers():
    set_parser_override(None)
    set_receipt_parser_override(None)
    yield
    set_parser_override(None)
    set_receipt_parser_override(None)


async def _wallets(session, tg):
    user, budget = await create_user(session, telegram_id=tg)
    uzs = make_wallet(budget, name="Карта сум")
    usd = make_wallet(budget, name="Копилка USD", currency="USD")
    session.add_all([uzs, usd])
    await session.flush()
    user.default_wallet_id = uzs.id
    await session.flush()
    return user, budget, uzs, usd


async def test_pending_type_question_shows_usd_for_a_usd_wallet(monkeypatch) -> None:
    async with rollback_session() as session:
        user, budget, _uzs, usd = await _wallets(session, 9_740_001)
        text = "50 на Копилка USD"
        set_parser_override(StubParser(responses={text: ParseResponse(operations=[
            ParsedOperation(type="ambiguous", amount=50, currency=None,
                            wallet_hint="Копилка USD", category=None, comment=None)
        ])}))
        monkeypatch.setattr("bot.quick_entry.handlers.async_session_factory", SessionFactory(session))
        message = make_message(telegram_id=user.telegram_id, text=text)
        await handle_quick_entry_text(message, SimpleNamespace())
        message.answer.assert_awaited_once()
        body = message.answer.await_args.args[0]
        assert "50 $" in body and "сум" not in body


async def test_photo_card_shows_usd_for_a_usd_wallet(monkeypatch) -> None:
    async with rollback_session() as session:
        user, budget, _uzs, usd = await _wallets(session, 9_740_002)
        set_receipt_parser_override(photo.FixedParser(ParseResponse(operations=[
            ParsedOperation(type="expense", amount=50, currency=None,
                            wallet_hint="Копилка USD", category=None, comment="Магнит")
        ], receipt_status="ok")))
        monkeypatch.setattr("bot.quick_entry.receipt_photo.PARSER_PROVIDER", "google")
        monkeypatch.setattr("bot.quick_entry.receipt_photo.PARSER_API_KEY", "test-key")
        monkeypatch.setattr("bot.quick_entry.receipt_photo.async_session_factory", SessionFactory(session))
        message = photo.make_photo_message(telegram_id=user.telegram_id)
        await handle_receipt_photo(message, photo.make_photo_bot())
        txns = list(await session.scalars(select(Transaction).where(Transaction.family_budget_id == budget.id)))
        assert len(txns) == 1 and txns[0].wallet_id == usd.id
        body = message.answer.await_args_list[-1].args[0]
        assert "50 $" in body and "50 сум" not in body
