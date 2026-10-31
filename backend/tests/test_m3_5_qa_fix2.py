"""QA m3-5: gaps in m3-4 fix2 coverage (found by mutation: overdue-open replay, completed replay)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.shopping import ShoppingPurchase
from tests.test_shopping import api_client, headers, pytestmark  # noqa: F401
from tests.test_shopping_pending import _flag_on_and_hint_recorder, two_items  # noqa: F401

BASE = "/api/v1/shopping/purchases/pending"


async def test_replay_of_overdue_open_wait_is_410_and_expires_it(api_client) -> None:
    client, session = api_client
    _fam, tid, ids = await two_items(client, session)
    token = str(uuid.uuid4())
    body = {"item_ids": ids, "method": "voice", "client_token": token}
    r1 = await client.post(BASE, headers=headers(tid), json=body)
    assert r1.status_code == 201
    row = await session.scalar(select(ShoppingPurchase).where(ShoppingPurchase.client_token == uuid.UUID(token)))
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await session.commit()
    r2 = await client.post(BASE, headers=headers(tid), json=body)
    assert r2.status_code == 410 and r2.json()["detail"] == "purchase_closed", r2.text
    session.expire_all()
    row = await session.scalar(select(ShoppingPurchase).where(ShoppingPurchase.client_token == uuid.UUID(token)))
    assert row.status == "expired"


async def test_replay_of_completed_token_is_idempotent_not_410(api_client) -> None:
    client, session = api_client
    _fam, tid, ids = await two_items(client, session)
    token = str(uuid.uuid4())
    body = {"item_ids": ids, "method": "voice", "client_token": token}
    r1 = await client.post(BASE, headers=headers(tid), json=body)
    assert r1.status_code == 201
    pid = r1.json()["id"]
    done = await client.post(f"{BASE}/{pid}/amount", headers=headers(tid), json={"amount": 50_000})
    assert done.status_code == 201, done.text
    r2 = await client.post(BASE, headers=headers(tid), json=body)
    assert r2.status_code == 200, r2.text
    assert r2.json()["id"] == pid
