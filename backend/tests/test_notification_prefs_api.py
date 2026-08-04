import socket
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_wallets_categories import api_client, auth_headers, create_user_with_budget


def _db_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            return True
    except OSError:
        return False


def _tid() -> int:
    return int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_me_defaults_notification_prefs_on(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    tid = _tid()
    await create_user_with_budget(session, telegram_id=tid, role="owner")
    await session.commit()
    r = await client.get("/api/v1/me", headers=auth_headers(tid))
    assert r.status_code == 200
    body = r.json()
    assert body["evening_reminder_enabled"] is True
    assert body["weekly_digest_enabled"] is True


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_patch_notification_prefs_independently(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    tid = _tid()
    await create_user_with_budget(session, telegram_id=tid, role="owner")
    await session.commit()
    r = await client.patch(
        "/api/v1/me",
        headers=auth_headers(tid),
        json={"evening_reminder_enabled": False},
    )
    assert r.status_code == 200
    assert r.json()["evening_reminder_enabled"] is False
    assert r.json()["weekly_digest_enabled"] is True
    r2 = await client.patch(
        "/api/v1/me",
        headers=auth_headers(tid),
        json={"weekly_digest_enabled": False},
    )
    assert r2.status_code == 200
    assert r2.json()["evening_reminder_enabled"] is False
    assert r2.json()["weekly_digest_enabled"] is False
