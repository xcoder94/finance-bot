"""QA m3-4: regressions for bugs found in the live pass (work/reports/m3-4-qa.md).

strict xfail = the bug is still there; when the fix lands the test turns XPASS -> FAILS -> drop the marker.
Real Postgres via rollback_session / api_client; only the AI parser and Telegram network are replaced.
"""

from __future__ import annotations

import time

import pytest
from aiogram.types import Message
from sqlalchemy import func, select, text

from app.models.shopping import ShoppingPurchase
from app.models.transaction import Transaction
from app.services.shopping import complete_pending_purchase, find_open_purchase
from bot.quick_entry.shopping_pending import finish_with_amount
from tests.test_m3_4_bot_pending import FakeBot, open_pending, setup_family
from tests.test_quick_entry_flow import pytestmark, rollback_session  # noqa: F401

BUG1 = "QA m3-4 B1: purchase row loaded by the bot is stale -> SELECT FOR UPDATE keeps status 'awaiting' -> 2nd expense"
BUG2 = "QA m3-4 B2: bot replay answers with ITS amount, not the recorded one"
BUG3 = "QA m3-4 B3: same client_token with another method silently returns the old method"


async def tx_count(session) -> int:
    return await session.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.type == "expense")
    )


async def test_competitor_completed_while_bot_held_the_row_no_second_expense() -> None:
    async with rollback_session() as session:
        user, _budget, ids = await setup_family(session, 9_460_001)
        purchase = await open_pending(session, user, ids, "voice")
        # the bot handler looked the purchase up (it now sits in this session's identity map) ...
        assert await find_open_purchase(session, user.id) is not None
        # ... meanwhile another transaction (the app's manual sum / a 2nd photo of an album) completed it
        competitor = Transaction(
            family_budget_id=user.family_budget_id, type="expense", wallet_id=user.default_wallet_id,
            amount=500_000, created_by_user_id=user.id, transaction_date=purchase.created_at,
        )
        session.add(competitor)
        await session.flush()
        await session.execute(
            text(
                "update shopping_purchases set status='completed', amount=500000, closed_at=now(), "
                "transaction_id=:tx, bought_item_names='{}' where id=:id"
            ),
            {"id": purchase.id, "tx": competitor.id},
        )
        before = await tx_count(session)
        _result, created = await complete_pending_purchase(
            session, user, purchase.id, amount=412_000, method="voice", channel="voice"
        )
        assert created is False  # replay of the completed purchase
        assert await tx_count(session) == before  # no second expense


async def test_bot_replay_reports_the_recorded_amount() -> None:
    async with rollback_session() as session:
        user, _budget, ids = await setup_family(session, 9_460_002)
        purchase = await open_pending(session, user, ids, "receipt")
        await complete_pending_purchase(session, user, purchase.id, amount=500_000, method="manual", channel="app")
        bot = FakeBot()
        message = Message.model_validate(
            {
                "message_id": 1, "date": int(time.time()), "chat": {"id": 42, "type": "private"},
                "from": {"id": user.telegram_id, "is_bot": False, "first_name": "T"}, "text": "412000",
            }
        ).as_(bot)
        await finish_with_amount(message, session, user, purchase, 412_000, channel="text")
        assert await tx_count(session) == 1
        assert len(bot.sent) == 1
        assert "500 000" in bot.sent[0].text, bot.sent[0].text


@pytest.mark.parametrize(
    "text,expected",
    [
        ("412000", 412_000), ("412 000", 412_000), ("412.000", 412_000), ("1,500,000", 1_500_000),
        ("12 3", None), ("41 2000", None), ("1 500 000", 1_500_000), ("1.5", None), ("412,50", None), ("31.10", None), ("1.5000", None), ("12.34.56", None),
    ],
)
def test_bare_amount_separator_only_before_three_digits(text, expected) -> None:
    from bot.quick_entry.shopping_pending import bare_text_amount

    assert bare_text_amount(text) == expected


def test_malformed_number_detector() -> None:
    from bot.quick_entry.shopping_pending import is_malformed_number

    assert is_malformed_number("1.5") and is_malformed_number("412,50")
    assert not is_malformed_number("412.000") and not is_malformed_number("412 тысяч")
