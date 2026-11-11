"""ux-r11: transfer / leave / remove / shopping hint never wait for Telegram (audit gap).

A hanging Telegram must not delay the API answer, the notice still goes out afterwards,
and the send is cut by the short timeout (the background work ends quickly).
"""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from app.services import goal_notify
from tests.test_phase9_members import (  # noqa: F401
    _db_available,
    _two_member_family,
    api_client,
    auth_headers,
)
from tests.test_shopping import add_items, make_family
from tests.test_shopping import api_client as shopping_client  # noqa: F401
from tests.test_shopping import headers as shopping_headers

pytestmark = [
    pytest.mark.skipif(not _db_available(), reason="DB not configured"),
    pytest.mark.anyio,
]

SLOW_LIMIT = 0.25  # the send timeout is 0.3 s: a faster answer did not wait for Telegram


def _hanging_bot(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    async def hang(*_a, **_k):  # noqa: ANN002, ANN003
        await asyncio.sleep(30)

    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=hang)

    async def fake_resolve_bot(b):  # noqa: ANN001
        return (bot if b is None else b), False

    monkeypatch.setattr("app.services.goal_notify.resolve_bot", fake_resolve_bot)
    monkeypatch.setattr(goal_notify, "NOTICE_TIMEOUT_SECONDS", 0.3)
    return bot


async def _drained_in_time() -> float:
    t0 = time.monotonic()
    await goal_notify.drain_background()
    return time.monotonic() - t0


async def test_transfer_request_answers_without_waiting_for_telegram(api_client, monkeypatch) -> None:  # noqa: F811
    client, session = api_client
    owner_tid, _owner, member, _budget = await _two_member_family(session)
    bot = _hanging_bot(monkeypatch)
    t0 = time.monotonic()
    resp = await client.post(f"/api/v1/members/{member.id}/transfer", headers=auth_headers(owner_tid))
    assert time.monotonic() - t0 < SLOW_LIMIT
    assert resp.status_code == 200 and resp.json()["status"] == "pending"
    assert await _drained_in_time() < 2  # cut by the timeout, not 30 s
    assert bot.send_message.await_count == 1
    assert bot.send_message.await_args.args[0] == member.telegram_id


async def test_leave_answers_without_waiting_for_telegram(api_client, monkeypatch) -> None:  # noqa: F811
    client, session = api_client
    owner_tid, _owner, member, _budget = await _two_member_family(session)
    bot = _hanging_bot(monkeypatch)
    t0 = time.monotonic()
    resp = await client.post("/api/v1/members/leave", headers=auth_headers(owner_tid + 1))
    assert time.monotonic() - t0 < SLOW_LIMIT
    assert resp.status_code == 200
    assert await _drained_in_time() < 2
    assert bot.send_message.await_count == 1
    assert bot.send_message.await_args.args[0] == member.telegram_id


async def test_remove_member_answers_without_waiting_for_telegram(api_client, monkeypatch) -> None:  # noqa: F811
    client, session = api_client
    owner_tid, _owner, member, _budget = await _two_member_family(session)
    bot = _hanging_bot(monkeypatch)
    t0 = time.monotonic()
    resp = await client.delete(f"/api/v1/members/{member.id}", headers=auth_headers(owner_tid))
    assert time.monotonic() - t0 < SLOW_LIMIT
    assert resp.status_code == 200
    assert await _drained_in_time() < 2
    assert bot.send_message.await_count == 1
    assert bot.send_message.await_args.args[0] == member.telegram_id


async def test_shopping_pending_hint_answers_without_waiting_for_telegram(
    shopping_client, monkeypatch  # noqa: F811
) -> None:
    client, session = shopping_client
    monkeypatch.setattr("app.config.RECEIPT_PHOTO_ENABLED", "true")
    fam = await make_family(session)
    tid = fam["user"].telegram_id
    items = await add_items(client, tid, "молоко")
    bot = _hanging_bot(monkeypatch)
    t0 = time.monotonic()
    resp = await client.post(
        "/api/v1/shopping/purchases/pending",
        headers=shopping_headers(tid),
        json={"item_ids": [items[0]["id"]], "method": "receipt"},
    )
    assert time.monotonic() - t0 < SLOW_LIMIT
    assert resp.status_code == 201, resp.text
    assert await _drained_in_time() < 2
    assert bot.send_message.await_count == 1
    assert bot.send_message.await_args.args[0] == tid
