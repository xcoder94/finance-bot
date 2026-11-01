"""Retention of the admin-panel tables (runs in the 04:00 Tashkent slot)."""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta

from sqlalchemy import bindparam, text
from sqlalchemy import Date
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _days_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        raise RuntimeError(f"{name} must be a positive integer (days)") from None
    if value < 1:
        raise RuntimeError(f"{name} must be a positive integer (days)")
    return value


ACTIVITY_RETENTION_DAYS = _days_env("ADMIN_ACTIVITY_RETENTION_DAYS", 400)
AI_USAGE_RETENTION_DAYS = _days_env("ADMIN_AI_USAGE_RETENTION_DAYS", 730)
AI_ALERTS_RETENTION_DAYS = _days_env("ADMIN_AI_ALERTS_RETENTION_DAYS", 730)
PURGE_BATCH = 5000

_ACTIVITY_BATCH = text(
    """
    DELETE FROM user_daily_activity WHERE (day, user_id) IN (
        SELECT day, user_id FROM user_daily_activity WHERE day < :cutoff LIMIT :n)
    """
).bindparams(bindparam("cutoff", type_=Date()))


def _cutoff(today: date, retention_days: int) -> date:
    # keep `retention_days` days including today: day >= today - (N - 1)
    return today - timedelta(days=retention_days - 1)


async def _purge_activity(session: AsyncSession, today: date) -> int:
    cutoff = _cutoff(today, ACTIVITY_RETENTION_DAYS)
    total = 0
    while True:
        res = await session.execute(_ACTIVITY_BATCH, {"cutoff": cutoff, "n": PURGE_BATCH})
        n = int(res.rowcount or 0)
        total += n
        if n < PURGE_BATCH:
            return total


async def _purge_by_day(session: AsyncSession, table: str, today: date, days: int) -> int:
    stmt = text(f"DELETE FROM {table} WHERE day < :cutoff").bindparams(  # noqa: S608 (constants)
        bindparam("cutoff", type_=Date())
    )
    res = await session.execute(stmt, {"cutoff": _cutoff(today, days)})
    return int(res.rowcount or 0)


async def _purge_ai_usage(session: AsyncSession, today: date) -> int:
    return await _purge_by_day(session, "ai_usage_daily", today, AI_USAGE_RETENTION_DAYS)


async def _purge_ai_alerts(session: AsyncSession, today: date) -> int:
    return await _purge_by_day(session, "ai_cost_alerts", today, AI_ALERTS_RETENTION_DAYS)


async def purge_admin_tables(session: AsyncSession, today: date) -> dict[str, int]:
    """Each table in its own savepoint: one failure does not stop the others (never raises)."""
    result: dict[str, int] = {}
    for name, fn in (
        ("user_daily_activity", _purge_activity),
        ("ai_usage_daily", _purge_ai_usage),
        ("ai_cost_alerts", _purge_ai_alerts),
    ):
        try:
            async with session.begin_nested():
                result[name] = await fn(session, today)
        except Exception:
            logger.exception("admin retention purge failed for %s", name)
    return result
