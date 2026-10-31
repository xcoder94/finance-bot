"""a-1: activity accounting (user_daily_activity, users.last_seen_at)."""

import socket
import time
from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Update
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_tracking import UserDailyActivity
from app.services import activity
from tests.admin_helpers import activity_on, make_user, utc
from tests.db_helpers import db_address
from tests.test_wallets_categories import api_client, auth_headers  # noqa: F401


def _db_available() -> bool:
    try:
        with socket.create_connection(db_address(), timeout=1):
            return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available"),
    pytest.mark.anyio,
]


async def _rows(session: AsyncSession, user_id) -> list[UserDailyActivity]:
    res = await session.execute(
        select(UserDailyActivity)
        .where(UserDailyActivity.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    return list(res.scalars())


async def _last_seen(session: AsyncSession, user) -> datetime | None:
    await session.refresh(user)
    return user.last_seen_at


async def test_two_requests_one_row_per_day(api_client, monkeypatch) -> None:
    client, session = api_client
    activity_on(monkeypatch, session)
    user = await make_user(session)
    h = auth_headers(user.telegram_id)
    assert (await client.get("/api/v1/me", headers=h)).status_code == 200
    assert (await client.get("/api/v1/me", headers=h)).status_code == 200
    rows = await _rows(session, user.id)
    assert len(rows) == 1
    assert rows[0].app is True and rows[0].bot is False
    assert rows[0].day == activity.tashkent_today()
    assert await _last_seen(session, user) is not None


async def test_current_user_dependency_also_counts(api_client, monkeypatch) -> None:
    client, session = api_client
    activity_on(monkeypatch, session)
    user = await make_user(session)
    resp = await client.get("/api/v1/wallets", headers=auth_headers(user.telegram_id))
    assert resp.status_code == 200
    rows = await _rows(session, user.id)
    assert [(r.app, r.bot) for r in rows] == [(True, False)]


async def test_bot_and_app_set_both_flags(api_client, monkeypatch) -> None:
    _, session = api_client
    activity_on(monkeypatch, session)
    user = await make_user(session)
    await activity.touch_activity(telegram_id=user.telegram_id, app=True)
    await activity.touch_activity(telegram_id=user.telegram_id, bot=True)
    rows = await _rows(session, user.id)
    assert len(rows) == 1
    assert (rows[0].app, rows[0].bot) == (True, True)


async def test_db_guard_without_cache_does_not_rewrite_fresh_last_seen(
    api_client, monkeypatch
) -> None:
    _, session = api_client
    activity_on(monkeypatch, session)
    user = await make_user(session)
    await activity.touch_activity(telegram_id=user.telegram_id, app=True)
    first = await _last_seen(session, user)
    activity.reset_cache()  # the DB guard alone must keep it unchanged
    await activity.touch_activity(telegram_id=user.telegram_id, app=True)
    assert await _last_seen(session, user) == first
    assert len(await _rows(session, user.id)) == 1


async def test_last_seen_refreshed_after_ten_minutes(api_client, monkeypatch) -> None:
    _, session = api_client
    activity_on(monkeypatch, session)
    user = await make_user(session)
    user.last_seen_at = datetime.now(UTC) - timedelta(minutes=11)
    await session.flush()
    await activity.touch_activity(telegram_id=user.telegram_id, app=True)
    seen = await _last_seen(session, user)
    assert seen is not None and datetime.now(UTC) - seen < timedelta(minutes=1)


async def test_cache_skips_the_database(api_client, monkeypatch) -> None:
    _, session = api_client
    activity_on(monkeypatch, session)
    user = await make_user(session)
    await activity.touch_activity(telegram_id=user.telegram_id, app=True)
    calls = 0
    real = activity._write

    async def counting(*a: Any, **k: Any):
        nonlocal calls
        calls += 1
        return await real(*a, **k)

    monkeypatch.setattr(activity, "_write", counting)
    await activity.touch_activity(telegram_id=user.telegram_id, app=True)
    assert calls == 0
    await activity.touch_activity(telegram_id=user.telegram_id, bot=True)  # other flag
    assert calls == 1


async def test_tashkent_day_boundary(api_client, monkeypatch) -> None:
    _, session = api_client
    activity_on(monkeypatch, session)
    user = await make_user(session)
    await activity.touch_activity(
        telegram_id=user.telegram_id, app=True, now=utc(2026, 6, 14, 18, 59, 59)
    )
    await activity.touch_activity(
        telegram_id=user.telegram_id, app=True, now=utc(2026, 6, 14, 19, 0, 0)
    )
    days = sorted(r.day for r in await _rows(session, user.id))
    assert days == [date(2026, 6, 14), date(2026, 6, 15)]


async def test_unknown_or_deleted_user_writes_nothing_and_is_not_cached(
    api_client, monkeypatch
) -> None:
    _, session = api_client
    activity_on(monkeypatch, session)
    ghost_tid = 4_000_000_001
    await activity.touch_activity(telegram_id=ghost_tid, bot=True)
    user = await make_user(session, telegram_id=ghost_tid)  # onboarded right after
    await activity.touch_activity(telegram_id=ghost_tid, bot=True)
    assert [(r.app, r.bot) for r in await _rows(session, user.id)] == [(False, True)]
    gone = await make_user(session, is_deleted=True)
    await activity.touch_activity(telegram_id=gone.telegram_id, bot=True)
    assert await _rows(session, gone.id) == []


async def test_accounting_failure_does_not_break_the_request(api_client, monkeypatch) -> None:
    client, session = api_client
    activity_on(monkeypatch, session)
    user = await make_user(session)

    class Boom:
        def __call__(self):
            raise RuntimeError("db down")

    monkeypatch.setattr(activity, "async_session_factory", Boom())
    resp = await client.get("/api/v1/me", headers=auth_headers(user.telegram_id))
    assert resp.status_code == 200
    await activity.touch_activity(telegram_id=user.telegram_id, bot=True)  # must not raise


# ---- bot side ---------------------------------------------------------------------------


class _FakeBot(Bot):
    def __init__(self) -> None:
        super().__init__(token="123456:TESTTOKEN")

    async def __call__(self, method: Any, request_timeout: Any = None) -> Any:
        return True


def _from(tid: int) -> dict[str, Any]:
    return {"id": tid, "is_bot": False, "first_name": "T"}


def _message_update(tid: int, **content: Any) -> Update:
    return Update.model_validate(
        {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "date": int(time.time()),
                "chat": {"id": tid, "type": "private"},
                "from": _from(tid),
                **content,
            },
        }
    )


def _callback_update(tid: int) -> Update:
    return Update.model_validate(
        {
            "update_id": 2,
            "callback_query": {
                "id": "1",
                "from": _from(tid),
                "chat_instance": "x",
                "data": "d",
            },
        }
    )


def _dispatcher(handled: list[str]) -> Dispatcher:
    from bot.activity_middleware import register_activity_middleware

    router = Router()

    @router.message()
    async def on_message(_m: Any) -> None:
        handled.append("m")

    @router.callback_query()
    async def on_cb(_c: Any) -> None:
        handled.append("c")

    dp = Dispatcher()
    register_activity_middleware(dp)
    dp.include_router(router)
    return dp


async def test_bot_text_voice_photo_and_callback_set_bot_flag(api_client, monkeypatch) -> None:
    _, session = api_client
    activity_on(monkeypatch, session)
    bot = _FakeBot()
    for build in (
        lambda t: _message_update(t, text="hi"),
        lambda t: _message_update(t, voice={"file_id": "f", "file_unique_id": "u", "duration": 1}),
        lambda t: _message_update(t, photo=[{"file_id": "f", "file_unique_id": "u", "width": 1, "height": 1}]),
        _callback_update,
    ):
        activity.reset_cache()
        user = await make_user(session)
        handled: list[str] = []
        dp = _dispatcher(handled)
        await dp.feed_update(bot, build(user.telegram_id))
        assert handled, "handler must still run"
        rows = await _rows(session, user.id)
        assert [(r.app, r.bot) for r in rows] == [(False, True)]
        assert await _last_seen(session, user) is not None


async def test_bot_accounting_failure_does_not_stop_the_handler(api_client, monkeypatch) -> None:
    _, session = api_client
    activity_on(monkeypatch, session)
    user = await make_user(session)

    async def boom(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(activity, "_write", boom)
    handled: list[str] = []
    dp = _dispatcher(handled)
    await dp.feed_update(_FakeBot(), _message_update(user.telegram_id, text="hi"))
    assert handled == ["m"]


async def test_new_user_created_by_the_handler_is_counted(api_client, monkeypatch) -> None:
    """/start creates the user inside the handler: accounting runs after it."""
    from bot.activity_middleware import register_activity_middleware

    _, session = api_client
    activity_on(monkeypatch, session)
    tid = 4_000_000_777
    router = Router()
    created: dict[str, Any] = {}

    @router.message()
    async def on_start(_m: Any) -> None:
        created["user"] = await make_user(session, telegram_id=tid)

    dp = Dispatcher()
    register_activity_middleware(dp)
    dp.include_router(router)
    await dp.feed_update(_FakeBot(), _message_update(tid, text="/start"))
    rows = await _rows(session, created["user"].id)
    assert [(r.app, r.bot) for r in rows] == [(False, True)]


def test_middleware_is_registered_in_bot_main() -> None:
    import inspect

    import bot.main as bot_main

    assert "register_activity_middleware" in inspect.getsource(bot_main.main)
