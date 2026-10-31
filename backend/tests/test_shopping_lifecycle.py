"""m3-4b: expiry sweeper, daily purge of closed purchases, membership cascades."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update

from app.models.family_budget import FamilyBudget
from app.models.shopping import ShoppingItem, ShoppingPurchase
from app.services.membership_lifecycle import (
    convert_join_with_own_budget,
    detach_member_to_own_budget,
)
from app.services.notification_scheduler import is_purge_slot, tick
from app.services.shopping import (
    create_pending_purchase,
    expire_open_purchases,
    find_open_purchase,
    purge_closed_purchases,
)
from tests.test_notification_scheduler import TASHKENT
from tests.test_quick_entry_flow import (
    create_user,
    pytestmark,  # noqa: F401
    rollback_session,
)
from unittest.mock import AsyncMock


async def add_item(session, budget, user, name="молоко") -> ShoppingItem:
    item = ShoppingItem(
        family_budget_id=budget.id, name=name, added_by_user_id=user.id,
        created_at=datetime.now(UTC),
    )
    session.add(item)
    await session.flush()
    return item


async def pending_for(session, user, item, method="voice") -> ShoppingPurchase:
    row, _ = await create_pending_purchase(
        session, user, item_ids=[item.id], method=method, client_token=None
    )
    return row


async def closed_row(session, user, budget, status, closed_ago: timedelta) -> ShoppingPurchase:
    now = datetime.now(UTC)
    row = ShoppingPurchase(
        family_budget_id=budget.id, created_by_user_id=user.id, client_token=uuid.uuid4(),
        status=status, method="voice", item_ids=[uuid.uuid4()],
        closed_at=now - closed_ago,
    )
    session.add(row)
    await session.flush()
    return row


class TestSweeper:
    async def test_only_overdue_open_rows_expire(self) -> None:
        async with rollback_session() as session:
            u1, b1 = await create_user(session, telegram_id=9_360_001)
            u2, b2 = await create_user(session, telegram_id=9_360_002)
            u3, b3 = await create_user(session, telegram_id=9_360_003)
            overdue = await pending_for(session, u1, await add_item(session, b1, u1))
            fresh = await pending_for(session, u2, await add_item(session, b2, u2))
            unrec = await pending_for(session, u3, await add_item(session, b3, u3))
            past = datetime.now(UTC) - timedelta(minutes=1)
            await session.execute(
                update(ShoppingPurchase)
                .where(ShoppingPurchase.id.in_([overdue.id, unrec.id]))
                .values(expires_at=past)
            )
            await session.execute(
                update(ShoppingPurchase).where(ShoppingPurchase.id == unrec.id).values(status="unrecognized")
            )
            n = await expire_open_purchases(session)
            assert n == 2
            for row in (overdue, fresh, unrec):
                await session.refresh(row)
            assert (overdue.status, unrec.status, fresh.status) == ("expired", "expired", "awaiting")
            assert overdue.closed_at is not None and fresh.closed_at is None
            assert await expire_open_purchases(session) == 0

    async def test_expired_row_frees_the_users_slot_and_bot_ignores_it(self) -> None:
        async with rollback_session() as session:
            u, b = await create_user(session, telegram_id=9_360_004)
            item = await add_item(session, b, u)
            row = await pending_for(session, u, item)
            await session.execute(
                update(ShoppingPurchase).where(ShoppingPurchase.id == row.id)
                .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
            await expire_open_purchases(session)
            assert await find_open_purchase(session, u.id) is None
            again = await pending_for(session, u, item)
            assert again.id != row.id and again.status == "awaiting"

    async def test_tick_runs_the_sweeper_every_minute(self) -> None:
        async with rollback_session() as session:
            u, b = await create_user(session, telegram_id=9_360_005)
            row = await pending_for(session, u, await add_item(session, b, u))
            await session.execute(
                update(ShoppingPurchase).where(ShoppingPurchase.id == row.id)
                .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
            await tick(session, datetime(2026, 8, 4, 15, 37, tzinfo=TASHKENT), AsyncMock())
            await session.refresh(row)
            assert row.status == "expired"


class TestPurge:
    async def test_slot_is_0400_tashkent(self) -> None:
        assert is_purge_slot(datetime(2026, 8, 4, 4, 0, tzinfo=TASHKENT))
        assert not is_purge_slot(datetime(2026, 8, 4, 4, 1, tzinfo=TASHKENT))
        assert not is_purge_slot(datetime(2026, 8, 4, 3, 0, tzinfo=TASHKENT))

    async def test_deletes_terminal_rows_older_than_30_days_only(self) -> None:
        async with rollback_session() as session:
            u, b = await create_user(session, telegram_id=9_360_006)
            old_done = await closed_row(session, u, b, "cancelled", timedelta(days=31))
            old_exp = await closed_row(session, u, b, "expired", timedelta(days=45))
            young = await closed_row(session, u, b, "cancelled", timedelta(days=29))
            open_row = await pending_for(session, u, await add_item(session, b, u))
            n = await purge_closed_purchases(session)
            assert n == 2
            left = set((await session.scalars(select(ShoppingPurchase.id))).all())
            assert left == {young.id, open_row.id}
            assert old_done.id not in left and old_exp.id not in left

    async def test_tick_purges_in_its_slot_only(self) -> None:
        async with rollback_session() as session:
            u, b = await create_user(session, telegram_id=9_360_007)
            old = await closed_row(session, u, b, "cancelled", timedelta(days=40))
            await tick(session, datetime(2026, 8, 4, 12, 0, tzinfo=TASHKENT), AsyncMock())
            assert await session.get(ShoppingPurchase, old.id) is not None
            await tick(session, datetime(2026, 8, 4, 4, 0, tzinfo=TASHKENT), AsyncMock())
            assert await session.scalar(
                select(func.count()).select_from(ShoppingPurchase).where(ShoppingPurchase.id == old.id)
            ) == 0

    async def test_purge_batches(self, monkeypatch) -> None:
        monkeypatch.setattr("app.services.shopping.PURGE_BATCH", 2)
        async with rollback_session() as session:
            u, b = await create_user(session, telegram_id=9_360_008)
            for _ in range(5):
                await closed_row(session, u, b, "expired", timedelta(days=60))
            assert await purge_closed_purchases(session) == 5
            assert await session.scalar(select(func.count()).select_from(ShoppingPurchase)) == 0


class TestCascades:
    async def test_detach_cancels_departing_users_open_purchase_keeps_items(self) -> None:
        async with rollback_session() as session:
            owner, budget = await create_user(session, telegram_id=9_361_001)
            member, _ = await create_user(session, telegram_id=9_361_002, role="member", budget=budget)
            owner_item = await add_item(session, budget, owner, "хлеб")
            member_item = await add_item(session, budget, member, "сыр")
            mine = await pending_for(session, member, member_item)
            theirs = await pending_for(session, owner, owner_item)

            await detach_member_to_own_budget(
                session, departing_user=member, old_budget=budget, reason="left", bot=AsyncMock()
            )
            await session.flush()

            await session.refresh(mine)
            await session.refresh(theirs)
            assert mine.status == "cancelled" and mine.closed_at is not None
            assert theirs.status == "awaiting"
            names = set(
                (await session.scalars(
                    select(ShoppingItem.name).where(ShoppingItem.family_budget_id == budget.id)
                )).all()
            )
            assert names == {"хлеб", "сыр"}  # the list belongs to the family

    async def test_convert_join_clears_old_list_and_cancels_purchase(self) -> None:
        async with rollback_session() as session:
            solo, solo_budget = await create_user(session, telegram_id=9_361_003)
            host, target = await create_user(session, telegram_id=9_361_004)
            old_item = await add_item(session, solo_budget, solo, "старое")
            host_item = await add_item(session, target, host, "чужое")
            row = await pending_for(session, solo, old_item)

            await convert_join_with_own_budget(session, user=solo, target=target)
            await session.flush()

            await session.refresh(row)
            assert row.status == "cancelled" and row.closed_at is not None
            assert await session.scalar(
                select(func.count()).select_from(ShoppingItem)
                .where(ShoppingItem.family_budget_id == solo_budget.id)
            ) == 0
            assert await session.get(ShoppingItem, host_item.id) is not None
            assert await session.get(FamilyBudget, solo_budget.id) is not None
