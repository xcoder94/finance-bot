"""a-2 backend-c: retention of the admin tables in the 04:00 Tashkent slot."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import delete, func, select

from app.models.admin_tracking import AiCostAlert, AiUsageDaily, UserDailyActivity
from app.services import admin_retention, notification_scheduler
from app.services.admin_retention import purge_admin_tables
from tests.admin_helpers import add_activity, make_user
from tests.test_a1_admin_overview import pytestmark  # noqa: F401
from tests.test_wallets_categories import api_client  # noqa: F401

TODAY = date(2026, 6, 15)
TZ = ZoneInfo("Asia/Tashkent")
SLOT = datetime(2026, 6, 15, 4, 0, tzinfo=TZ)


async def _clean(session) -> None:
    await session.execute(delete(UserDailyActivity))
    await session.execute(delete(AiUsageDaily))
    await session.execute(delete(AiCostAlert))
    await session.flush()


def _usage(day: date) -> AiUsageDaily:
    return AiUsageDaily(day=day, model="m", kind="text", outcome="ok")


def _alert(day: date) -> AiCostAlert:
    return AiCostAlert(day=day, threshold_micro_usd=1, cost_micro_usd=2)


async def _days(session, model) -> set[date]:
    return set((await session.scalars(select(model.day))).all())


async def test_activity_boundary_400_days(api_client) -> None:
    _, session = api_client
    await _clean(session)
    user = await make_user(session)
    keep, drop = TODAY - timedelta(days=399), TODAY - timedelta(days=400)
    for d in (keep, drop):
        await add_activity(session, user, d)
    await purge_admin_tables(session, TODAY)
    assert await _days(session, UserDailyActivity) == {keep}


async def test_ai_tables_boundary_730_days(api_client) -> None:
    _, session = api_client
    await _clean(session)
    keep, drop = TODAY - timedelta(days=729), TODAY - timedelta(days=730)
    session.add_all([_usage(keep), _usage(drop), _alert(keep), _alert(drop)])
    await session.flush()
    await purge_admin_tables(session, TODAY)
    assert await _days(session, AiUsageDaily) == {keep}
    assert await _days(session, AiCostAlert) == {keep}


async def test_batches_delete_everything_old(api_client, monkeypatch) -> None:
    _, session = api_client
    await _clean(session)
    monkeypatch.setattr(admin_retention, "PURGE_BATCH", 2)
    user = await make_user(session)
    old = [TODAY - timedelta(days=401 + i) for i in range(5)]
    for d in old:
        await add_activity(session, user, d)
    await add_activity(session, user, TODAY)
    await purge_admin_tables(session, TODAY)
    assert await _days(session, UserDailyActivity) == {TODAY}


async def test_other_tables_untouched(api_client) -> None:
    _, session = api_client
    user = await make_user(session)
    await purge_admin_tables(session, TODAY)
    await session.refresh(user)
    assert user.id is not None


async def test_failure_does_not_stop_other_purges(api_client, monkeypatch) -> None:
    _, session = api_client
    await _clean(session)
    drop = TODAY - timedelta(days=800)
    session.add_all([_usage(drop), _alert(drop)])
    await session.flush()

    async def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(admin_retention, "_purge_activity", boom)
    await purge_admin_tables(session, TODAY)  # must not raise
    assert await _days(session, AiUsageDaily) == set()
    assert await _days(session, AiCostAlert) == set()


async def test_tick_runs_purge_in_slot_only_and_survives_failure(api_client, monkeypatch) -> None:
    _, session = api_client
    calls = []

    async def fake(s, today):
        calls.append(today)

    monkeypatch.setattr(notification_scheduler, "purge_admin_tables", fake)
    await notification_scheduler.tick(session, datetime(2026, 6, 15, 12, 0, tzinfo=TZ), AsyncMock())
    assert calls == []
    await notification_scheduler.tick(session, SLOT, AsyncMock())
    assert calls == [TODAY]

    async def bad(s, today):
        raise RuntimeError("x")

    monkeypatch.setattr(notification_scheduler, "purge_admin_tables", bad)
    await notification_scheduler.tick(session, SLOT, AsyncMock())  # must not raise
