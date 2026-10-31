"""Shared fixtures-as-functions for the admin panel tests (a-1)."""

import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_tracking import UserDailyActivity
from app.models.family_budget import FamilyBudget
from app.models.user import User
from tests.test_telegram_auth import _AsyncSessionFactoryOverride


def rand_tid() -> int:
    return int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000


def utc(y: int, m: int, d: int, hh: int = 0, mm: int = 0, ss: int = 0) -> datetime:
    return datetime(y, m, d, hh, mm, ss, tzinfo=UTC)


def tashkent_noon(y: int, m: int, d: int) -> datetime:
    """12:00 Tashkent (UTC+5) = 07:00 UTC."""
    return utc(y, m, d, 7)


async def make_user(
    session: AsyncSession,
    *,
    created_at: datetime | None = None,
    family: FamilyBudget | None = None,
    role: str = "owner",
    first_name: str | None = None,
    username: str | None = None,
    phone: str | None = None,
    language: str = "ru",
    is_deleted: bool = False,
    family_created_at: datetime | None = None,
    family_deleted: bool = False,
    telegram_id: int | None = None,
) -> User:
    if family is None:
        kwargs: dict[str, Any] = {"invite_token": f"t-{uuid.uuid4()}"}
        if family_created_at is not None or created_at is not None:
            kwargs["created_at"] = family_created_at or created_at
        if family_deleted:
            kwargs["is_deleted"] = True
        family = FamilyBudget(**kwargs)
        session.add(family)
        await session.flush()
    extra: dict[str, Any] = {}
    if created_at is not None:
        extra["created_at"] = created_at
    if phone is not None:
        extra["phone"] = phone
        extra["phone_shared_at"] = created_at or datetime.now(UTC)
    user = User(
        telegram_id=telegram_id or rand_tid(),
        family_budget_id=family.id,
        role=role,
        first_name=first_name,
        username=username,
        language=language,
        is_deleted=is_deleted,
        **extra,
    )
    session.add(user)
    await session.flush()
    return user


async def add_activity(
    session: AsyncSession, user: User, day: date, *, app: bool = True, bot: bool = False
) -> None:
    session.add(UserDailyActivity(user_id=user.id, day=day, app=app, bot=bot))
    await session.flush()


def activity_on(monkeypatch: pytest.MonkeyPatch, session: AsyncSession) -> None:
    """Enable accounting; its own session is replaced by the test session."""
    from app.services import activity

    monkeypatch.setattr(activity, "TRACKING_ENABLED", True)
    monkeypatch.setattr(activity, "async_session_factory", _AsyncSessionFactoryOverride(session))
    activity.reset_cache()


def make_admin(monkeypatch: pytest.MonkeyPatch, *telegram_ids: int) -> None:
    from app import config

    monkeypatch.setattr(config, "ADMIN_TELEGRAM_IDS", frozenset(telegram_ids))


def walk_keys(node: Any):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from walk_keys(v)
    elif isinstance(node, list):
        for item in node:
            yield from walk_keys(item)


FORBIDDEN_KEY_PARTS = ("amount", "balance", "category", "comment", "wallet", "budget_name")
