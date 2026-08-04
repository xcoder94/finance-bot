import socket
import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.evening_reminder import EVENING_REMINDER_TEXT
from app.services.notification_scheduler import (
    _default_clock,
    is_evening_reminder_slot,
    is_weekly_digest_slot,
    tick,
)
from app.services.weekly_digest import DIGEST_TITLE
from tests.test_wallets_categories import api_client, create_user_with_budget

TASHKENT = ZoneInfo("Asia/Tashkent")

EVENING_SLOT = datetime(2026, 8, 4, 21, 0, tzinfo=TASHKENT)
MONDAY_SLOT = datetime(2026, 8, 3, 10, 0, tzinfo=TASHKENT)


def _db_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            return True
    except OSError:
        return False


def _tid() -> int:
    return int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000


def test_evening_slot_only_at_2100_tashkent() -> None:
    assert is_evening_reminder_slot(datetime(2026, 8, 4, 21, 0, tzinfo=TASHKENT))
    assert not is_evening_reminder_slot(datetime(2026, 8, 4, 21, 1, tzinfo=TASHKENT))
    assert not is_evening_reminder_slot(datetime(2026, 8, 4, 20, 0, tzinfo=TASHKENT))


def test_weekly_slot_monday_1000() -> None:
    assert is_weekly_digest_slot(datetime(2026, 8, 3, 10, 0, tzinfo=TASHKENT))
    assert not is_weekly_digest_slot(datetime(2026, 8, 4, 10, 0, tzinfo=TASHKENT))


def test_default_clock_is_tashkent_aware() -> None:
    now = _default_clock()
    assert now.tzinfo is not None
    assert now.utcoffset() == datetime.now(TASHKENT).utcoffset()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_tick_evening_no_activity_sends_reminder(
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
    await tick(session, EVENING_SLOT, bot)
    await session.commit()

    our_ids = {owner.telegram_id, member.telegram_id}
    our_calls = [
        c for c in bot.send_message.await_args_list if c.args[0] in our_ids
    ]
    assert len(our_calls) == 2
    for call in our_calls:
        assert call.args[1] == EVENING_REMINDER_TEXT
        assert call.kwargs.get("parse_mode") == "Markdown"

    refreshed = await session.get(FamilyBudget, budget.id)
    assert refreshed is not None
    assert refreshed.last_evening_reminder_on == date(2026, 8, 4)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_tick_evening_second_tick_same_day_no_duplicate(
    api_client: tuple[object, AsyncSession],
) -> None:
    _, session = api_client
    owner_tid = _tid()
    owner, budget = await create_user_with_budget(
        session, telegram_id=owner_tid, role="owner"
    )
    await session.flush()

    bot = AsyncMock()
    await tick(session, EVENING_SLOT, bot)
    await session.commit()

    our_calls = [
        c
        for c in bot.send_message.await_args_list
        if c.args[0] == owner.telegram_id
    ]
    assert len(our_calls) == 1

    await tick(session, EVENING_SLOT, bot)
    await session.commit()

    our_calls_after = [
        c
        for c in bot.send_message.await_args_list
        if c.args[0] == owner.telegram_id
    ]
    assert len(our_calls_after) == 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_tick_evening_personal_activity_no_send(
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

    bot = AsyncMock()
    await tick(session, EVENING_SLOT, bot)
    await session.commit()

    our_calls = [
        c
        for c in bot.send_message.await_args_list
        if c.args[0] == owner.telegram_id
    ]
    assert len(our_calls) == 0

    refreshed = await session.get(FamilyBudget, budget.id)
    assert refreshed is not None
    assert refreshed.last_evening_reminder_on == date(2026, 8, 4)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_tick_weekly_monday_sends_digest(
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
    await tick(session, MONDAY_SLOT, bot)
    await session.commit()

    our_ids = {owner.telegram_id, member.telegram_id}
    our_calls = [
        c for c in bot.send_message.await_args_list if c.args[0] in our_ids
    ]
    assert len(our_calls) == 2
    for call in our_calls:
        assert call.args[1].startswith(DIGEST_TITLE)

    refreshed = await session.get(FamilyBudget, budget.id)
    assert refreshed is not None
    assert refreshed.last_weekly_digest_on == date(2026, 8, 3)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_tick_weekly_second_tick_same_day_no_duplicate(
    api_client: tuple[object, AsyncSession],
) -> None:
    _, session = api_client
    owner_tid = _tid()
    owner, budget = await create_user_with_budget(
        session, telegram_id=owner_tid, role="owner"
    )
    await session.flush()

    bot = AsyncMock()
    await tick(session, MONDAY_SLOT, bot)
    await session.commit()

    our_calls = [
        c
        for c in bot.send_message.await_args_list
        if c.args[0] == owner.telegram_id
    ]
    assert len(our_calls) == 1

    await tick(session, MONDAY_SLOT, bot)
    await session.commit()

    our_calls_after = [
        c
        for c in bot.send_message.await_args_list
        if c.args[0] == owner.telegram_id
    ]
    assert len(our_calls_after) == 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_tick_non_slot_no_action(
    api_client: tuple[object, AsyncSession],
) -> None:
    _, session = api_client
    _, budget = await create_user_with_budget(session, telegram_id=_tid(), role="owner")
    await session.flush()

    bot = AsyncMock()
    off_slot = datetime(2026, 8, 4, 12, 0, tzinfo=TASHKENT)
    await tick(session, off_slot, bot)
    await session.commit()

    bot.send_message.assert_not_awaited()

    refreshed = await session.get(FamilyBudget, budget.id)
    assert refreshed is not None
    assert refreshed.last_evening_reminder_on is None
    assert refreshed.last_weekly_digest_on is None
