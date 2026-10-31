"""Activity accounting: one row per user per Tashkent day + users.last_seen_at.

Contract: work/db/admin-schema.md (W1). Throttled by an in-process cache so most
requests never touch the database; the SQL carries its own guards, so a cache miss
(restart, another process) is still cheap. Accounting never raises into its caller.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import bindparam, select, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy import Boolean, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_factory
from app.models.user import User

logger = logging.getLogger(__name__)

TASHKENT = ZoneInfo("Asia/Tashkent")
CACHE_TTL_SECONDS = 600
_CACHE_MAX_ENTRIES = 200_000

# Tests that run inside a rolled-back transaction switch this off (tests/conftest.py).
TRACKING_ENABLED = True

_cache: dict[tuple[int, date, str], float] = {}

# W1 from work/db/admin-schema.md, verbatim apart from explicit parameter types.
_TOUCH_SQL = text(
    """
    WITH seen AS (
      UPDATE users SET last_seen_at = now()
       WHERE id = :uid AND (last_seen_at IS NULL OR last_seen_at < now() - interval '10 minutes')
      RETURNING id)
    INSERT INTO user_daily_activity AS a (user_id, day, app, bot) VALUES (:uid, :day, :app, :bot)
    ON CONFLICT (user_id, day) DO UPDATE
      SET app = a.app OR excluded.app, bot = a.bot OR excluded.bot
      WHERE (excluded.app AND NOT a.app) OR (excluded.bot AND NOT a.bot)
    """
).bindparams(
    bindparam("uid", type_=PG_UUID(as_uuid=True)),
    bindparam("day", type_=Date()),
    bindparam("app", type_=Boolean()),
    bindparam("bot", type_=Boolean()),
)


def utcnow() -> datetime:
    return datetime.now(UTC)


def tashkent_today(now: datetime | None = None) -> date:
    return (now or utcnow()).astimezone(TASHKENT).date()


def reset_cache() -> None:
    _cache.clear()


def _fresh(key: tuple[int, date, str], mono: float) -> bool:
    stamp = _cache.get(key)
    return stamp is not None and mono - stamp < CACHE_TTL_SECONDS


async def _write(session: AsyncSession, user_id: uuid.UUID, day: date, app: bool, bot: bool) -> None:
    await session.execute(_TOUCH_SQL, {"uid": user_id, "day": day, "app": app, "bot": bot})


async def touch_activity(
    *,
    telegram_id: int,
    user_id: uuid.UUID | None = None,
    app: bool = False,
    bot: bool = False,
    now: datetime | None = None,
) -> None:
    """Record that the user was active today via the app and/or the bot. Never raises."""
    if not TRACKING_ENABLED or not (app or bot):
        return
    try:
        day = tashkent_today(now)
        mono = time.monotonic()
        flags = [name for name, on in (("app", app), ("bot", bot)) if on]
        if all(_fresh((telegram_id, day, f), mono) for f in flags):
            return
        async with async_session_factory() as session:
            if user_id is None:
                user_id = await session.scalar(
                    select(User.id).where(User.telegram_id == telegram_id, User.is_deleted.is_(False))
                )
                if user_id is None:
                    return  # not onboarded yet (or removed): nothing to account, nothing cached
            await _write(session, user_id, day, app, bot)
            await session.commit()
        if len(_cache) >= _CACHE_MAX_ENTRIES:
            _cache.clear()
        stamp = time.monotonic()
        for f in flags:
            _cache[(telegram_id, day, f)] = stamp
    except Exception as exc:
        logger.warning("activity accounting failed: %s", type(exc).__name__)
