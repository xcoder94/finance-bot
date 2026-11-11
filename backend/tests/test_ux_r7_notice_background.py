"""API answers never wait for Telegram; notices go out after commit, exactly once (ux-r7)."""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import goal_notify
from tests.test_goal_achievement_no_switch import (
    _create_owner_and_member_both_switches_off,
    _create_shared_wallet,
    _db_available,
    _seed_income,
)
from tests.test_wallets_categories import api_client, auth_headers  # noqa: F401

pytestmark = [
    pytest.mark.skipif(not _db_available(), reason="DB not configured"),
    pytest.mark.anyio,
]


def _bot(monkeypatch: pytest.MonkeyPatch, send) -> AsyncMock:  # noqa: ANN001
    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=send)

    async def fake_resolve_bot(b):  # noqa: ANN001
        return (bot if b is None else b), False

    monkeypatch.setattr("app.services.goal_notify.resolve_bot", fake_resolve_bot)
    return bot


async def _setup(session: AsyncSession):  # noqa: ANN202
    owner_tid, _m, owner, _ = await _create_owner_and_member_both_switches_off(session)
    wallet = await _create_shared_wallet(session, owner.family_budget_id)
    await _seed_income(session, owner.family_budget_id, wallet.id, owner.id, 9_000_000)
    return owner_tid, wallet


async def test_hanging_telegram_does_not_delay_answer(
    api_client: tuple[AsyncClient, AsyncSession], monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    client, session = api_client
    owner_tid, wallet = await _setup(session)

    async def hang(*a, **kw):  # noqa: ANN002, ANN003
        await asyncio.sleep(30)

    bot = _bot(monkeypatch, hang)
    monkeypatch.setattr(goal_notify, "NOTICE_TIMEOUT_SECONDS", 0.3)

    t0 = time.monotonic()
    resp = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={"wallet_id": str(wallet.id), "target_amount": 8_000_000},
    )
    elapsed = time.monotonic() - t0
    assert resp.status_code == 201, resp.text
    assert elapsed < 0.25  # answer is faster than the send timeout: it did not wait
    # background sends are cut by the timeout and the process is fine afterwards
    await goal_notify.drain_background()
    assert bot.send_message.await_count == 2
    again = await client.get("/api/v1/goals?status=active", headers=auth_headers(owner_tid))
    assert again.status_code == 200


async def test_successful_send_delivers_exactly_once_per_recipient(
    api_client: tuple[AsyncClient, AsyncSession], monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    client, session = api_client
    owner_tid, wallet = await _setup(session)
    bot = _bot(monkeypatch, AsyncMock())

    resp = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={"wallet_id": str(wallet.id), "target_amount": 8_000_000},
    )
    assert resp.status_code == 201, resp.text
    await goal_notify.drain_background()
    chat_ids = sorted(c.args[0] for c in bot.send_message.await_args_list)
    assert len(chat_ids) == 2 and len(set(chat_ids)) == 2


async def test_rolled_back_change_sends_nothing(
    api_client: tuple[AsyncClient, AsyncSession], monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    _client, session = api_client
    bot = _bot(monkeypatch, AsyncMock())
    await session.execute(text("select 1"))
    goal_notify.queue_notice(session, None, 1, "x")
    await session.rollback()
    await session.commit()
    await goal_notify.drain_background()
    assert bot.send_message.await_count == 0
