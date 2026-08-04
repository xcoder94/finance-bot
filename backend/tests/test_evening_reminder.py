import socket
import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.evening_reminder import (
    EVENING_REMINDER_TEXT,
    family_had_activity_on,
    send_evening_reminders_for_family,
)
from tests.test_wallets_categories import api_client, create_user_with_budget

TASHKENT = ZoneInfo("Asia/Tashkent")

EXPECTED = (
    "Сегодня не было ни одной записи.\n"
    "Напишите трату одной строкой — например, `продукты 150 тысяч`"
)

TEST_DAY = date(2026, 8, 4)


def _db_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            return True
    except OSError:
        return False


def _tid() -> int:
    return int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000


def test_evening_text_exact() -> None:
    assert EVENING_REMINDER_TEXT == EXPECTED


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_send_evening_reminders_no_activity_fan_out(
    api_client: tuple[object, AsyncSession],
) -> None:
    _, session = api_client
    owner_tid = _tid()
    member_tid = owner_tid + 1
    owner, budget = await create_user_with_budget(
        session, telegram_id=owner_tid, role="owner"
    )
    member = User(
        telegram_id=member_tid,
        family_budget_id=budget.id,
        role="member",
        language="ru",
    )
    session.add(member)
    await session.flush()

    bot = AsyncMock()
    count = await send_evening_reminders_for_family(
        session, budget, TEST_DAY, bot
    )

    assert count == 2
    assert bot.send_message.await_count == 2
    for call in bot.send_message.await_args_list:
        assert call.args[1] == EXPECTED
        assert call.kwargs.get("parse_mode") == "Markdown"
    sent_ids = {call.args[0] for call in bot.send_message.await_args_list}
    assert sent_ids == {owner.telegram_id, member.telegram_id}


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_family_had_activity_on_personal_wallet_expense(
    api_client: tuple[object, AsyncSession],
) -> None:
    _, session = api_client
    owner_tid = _tid()
    owner, budget = await create_user_with_budget(
        session, telegram_id=owner_tid, role="owner"
    )
    personal = Wallet(
        family_budget_id=budget.id,
        name="Personal",
        currency="UZS",
        is_personal=True,
        owner_user_id=owner.id,
    )
    food = ExpenseCategory(family_budget_id=budget.id, name="Food")
    session.add_all([personal, food])
    await session.flush()
    txn = Transaction(
        family_budget_id=budget.id,
        type="expense",
        wallet_id=personal.id,
        amount=50_000,
        expense_category_id=food.id,
        created_by_user_id=owner.id,
        transaction_date=datetime(2026, 8, 4, 15, 30, tzinfo=TASHKENT),
    )
    session.add(txn)
    await session.flush()

    assert await family_had_activity_on(session, budget.id, TEST_DAY) is True


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_send_skips_user_with_evening_reminder_disabled(
    api_client: tuple[object, AsyncSession],
) -> None:
    _, session = api_client
    owner_tid = _tid()
    member_tid = owner_tid + 1
    owner, budget = await create_user_with_budget(
        session, telegram_id=owner_tid, role="owner"
    )
    owner.evening_reminder_enabled = False
    member = User(
        telegram_id=member_tid,
        family_budget_id=budget.id,
        role="member",
        language="ru",
        evening_reminder_enabled=True,
    )
    session.add(member)
    await session.flush()

    bot = AsyncMock()
    count = await send_evening_reminders_for_family(
        session, budget, TEST_DAY, bot
    )

    assert count == 1
    bot.send_message.assert_awaited_once_with(
        member.telegram_id,
        EXPECTED,
        parse_mode="Markdown",
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_family_had_activity_on_false_when_no_transactions(
    api_client: tuple[object, AsyncSession],
) -> None:
    _, session = api_client
    _, budget = await create_user_with_budget(session, telegram_id=_tid(), role="owner")
    await session.flush()

    assert await family_had_activity_on(session, budget.id, TEST_DAY) is False
