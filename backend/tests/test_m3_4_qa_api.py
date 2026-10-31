"""QA m3-4 (API side), see tests/test_m3_4_qa.py for the convention (strict xfail = bug still present)."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models.shopping import ShoppingPurchase
from tests.test_shopping import api_client, headers, pytestmark  # noqa: F401
from tests.test_shopping_pending import _flag_on_and_hint_recorder, two_items  # noqa: F401

BUG3 = "QA m3-4 B3: same client_token with another method silently returns the old method"


async def test_same_token_other_method_does_not_keep_the_old_method(api_client) -> None:
    client, session = api_client
    _fam, tid, ids = await two_items(client, session)
    token = str(uuid.uuid4())
    base = "/api/v1/shopping/purchases/pending"
    r1 = await client.post(base, headers=headers(tid), json={"item_ids": ids, "method": "voice", "client_token": token})
    assert r1.status_code == 201
    r2 = await client.post(base, headers=headers(tid), json={"item_ids": ids, "method": "receipt", "client_token": token})
    open_row = await session.scalar(
        select(ShoppingPurchase).where(ShoppingPurchase.status.in_(("awaiting", "unrecognized")))
    )
    assert r2.status_code == 409 and r2.json()["detail"] == "token_conflict", r2.text
    assert open_row.method == "voice"  # state unchanged


async def test_same_token_other_items_conflicts(api_client) -> None:
    client, session = api_client
    _fam, tid, ids = await two_items(client, session)
    token = str(uuid.uuid4())
    base = "/api/v1/shopping/purchases/pending"
    r1 = await client.post(base, headers=headers(tid), json={"item_ids": ids, "method": "voice", "client_token": token})
    assert r1.status_code == 201
    r2 = await client.post(base, headers=headers(tid), json={"item_ids": ids[:1], "method": "voice", "client_token": token})
    assert r2.status_code == 409 and r2.json()["detail"] == "token_conflict", r2.text


async def test_same_token_same_data_is_idempotent(api_client) -> None:
    client, session = api_client
    _fam, tid, ids = await two_items(client, session)
    token = str(uuid.uuid4())
    base = "/api/v1/shopping/purchases/pending"
    body = {"item_ids": ids, "method": "voice", "client_token": token}
    r1 = await client.post(base, headers=headers(tid), json=body)
    r2 = await client.post(base, headers=headers(tid), json={**body, "item_ids": list(reversed(ids))})
    assert (r1.status_code, r2.status_code) == (201, 200)
    assert r1.json()["id"] == r2.json()["id"]


async def test_new_token_replaces_live_pending(api_client) -> None:
    client, session = api_client
    _fam, tid, ids = await two_items(client, session)
    base = "/api/v1/shopping/purchases/pending"
    r1 = await client.post(base, headers=headers(tid), json={"item_ids": ids, "method": "voice", "client_token": str(uuid.uuid4())})
    r2 = await client.post(base, headers=headers(tid), json={"item_ids": ids, "method": "receipt", "client_token": str(uuid.uuid4())})
    assert (r1.status_code, r2.status_code) == (201, 201)
    rows = (await session.scalars(select(ShoppingPurchase).where(ShoppingPurchase.status.in_(("awaiting", "unrecognized"))))).all()
    assert [r.method for r in rows] == ["photo"]


@pytest.mark.parametrize("closed_status", ["cancelled", "expired"])
async def test_replay_of_closed_token_is_410_purchase_closed(api_client, closed_status) -> None:
    client, session = api_client
    _fam, tid, ids = await two_items(client, session)
    token = str(uuid.uuid4())
    base = "/api/v1/shopping/purchases/pending"
    body = {"item_ids": ids, "method": "voice", "client_token": token}
    r1 = await client.post(base, headers=headers(tid), json=body)
    assert r1.status_code == 201
    row = await session.scalar(select(ShoppingPurchase).where(ShoppingPurchase.client_token == uuid.UUID(token)))
    row.status = closed_status
    row.closed_at = datetime.now(UTC)
    await session.commit()
    r2 = await client.post(base, headers=headers(tid), json=body)
    assert r2.status_code == 410 and r2.json()["detail"] == "purchase_closed", r2.text
