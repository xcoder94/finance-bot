"""ux-next3b: a purchase with items of an old/foreign family records nothing (HTTP, real Postgres)."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from app.models.shopping import ShoppingItem
from app.models.transaction import Transaction
from app.models.user import User
from app.services.membership_lifecycle import (
    convert_join_with_own_budget,
    detach_member_to_own_budget,
)
from tests.test_shopping import add_items, api_client, buy, headers, make_family  # noqa: F401

pytestmark = pytest.mark.anyio


async def _tx_count(session) -> int:
    return await session.scalar(select(func.count()).select_from(Transaction))


async def _purchase_count(session) -> int:
    from app.models.shopping import ShoppingPurchase

    return await session.scalar(select(func.count()).select_from(ShoppingPurchase))


async def _assert_rejected(client, session, tid, ids, codes=(404, 409)) -> None:
    tx_before = await _tx_count(session)
    pu_before = await _purchase_count(session)
    r = await buy(client, tid, ids)
    assert r.status_code in codes, r.text
    assert await _tx_count(session) == tx_before
    assert await _purchase_count(session) == pu_before


async def test_after_join_old_ids_record_nothing(api_client) -> None:
    client, session = api_client
    solo = await make_family(session)
    host = await make_family(session)
    tid = solo["user"].telegram_id
    items = await add_items(client, tid, "хлеб", "сыр")
    ids = [i["id"] for i in items]
    await session.flush()

    await convert_join_with_own_budget(session, user=solo["user"], target=host["budget"])
    await session.flush()

    await _assert_rejected(client, session, tid, ids, codes=(404,))


async def test_after_leave_old_ids_record_nothing(api_client) -> None:
    client, session = api_client
    fam = await make_family(session, second_member=True)
    member = fam["other"]
    items = await add_items(client, fam["user"].telegram_id, "хлеб")
    await session.flush()

    await detach_member_to_own_budget(
        session, departing_user=member, old_budget=fam["budget"], reason="left", bot=AsyncMock()
    )
    await session.flush()

    await _assert_rejected(client, session, member.telegram_id, [items[0]["id"]], codes=(404,))
    assert await session.scalar(
        select(func.count()).select_from(ShoppingItem)
        .where(ShoppingItem.family_budget_id == fam["budget"].id)
    ) == 1


async def test_after_removal_old_ids_record_nothing(api_client) -> None:
    client, session = api_client
    fam = await make_family(session, second_member=True)
    member = fam["other"]
    items = await add_items(client, fam["user"].telegram_id, "хлеб")
    await session.flush()

    await detach_member_to_own_budget(
        session, departing_user=member, old_budget=fam["budget"], reason="removed", bot=AsyncMock()
    )
    await session.flush()

    await _assert_rejected(client, session, member.telegram_id, [items[0]["id"]], codes=(404,))


async def test_one_stale_id_among_valid_rejects_everything(api_client) -> None:
    client, session = api_client
    fam = await make_family(session)
    tid = fam["user"].telegram_id
    items = await add_items(client, tid, "хлеб", "сыр")
    ids = [i["id"] for i in items]
    # one of the items is gone (bought/removed elsewhere)
    r = await client.delete(f"/api/v1/shopping/items/{ids[1]}", headers=headers(tid))
    assert r.status_code == 204

    await _assert_rejected(client, session, tid, ids, codes=(404,))
    still = await client.get("/api/v1/shopping/items", headers=headers(tid))
    assert [i["id"] for i in still.json()] == [ids[0]]


async def test_pending_with_stale_ids_is_rejected(api_client) -> None:
    client, session = api_client
    solo = await make_family(session)
    host = await make_family(session)
    tid = solo["user"].telegram_id
    items = await add_items(client, tid, "хлеб")
    await session.flush()
    await convert_join_with_own_budget(session, user=solo["user"], target=host["budget"])
    await session.flush()

    r = await client.post(
        "/api/v1/shopping/purchases/pending",
        headers=headers(tid),
        json={"item_ids": [items[0]["id"]], "method": "voice"},
    )
    assert r.status_code == 404, r.text
    assert await _purchase_count(session) == 0


async def test_neighbour_paths_reject_stale_ids_and_write_nothing(api_client) -> None:
    client, session = api_client
    solo = await make_family(session)
    host = await make_family(session)
    tid = solo["user"].telegram_id
    items = await add_items(client, tid, "хлеб")
    hitems = await add_items(client, host["user"].telegram_id, "чужое")
    await session.flush()
    await convert_join_with_own_budget(session, user=solo["user"], target=host["budget"])
    await session.flush()

    old = items[0]["id"]
    assert (await client.patch(
        f"/api/v1/shopping/items/{old}", headers=headers(tid), json={"name": "x"}
    )).status_code == 404
    assert (await client.delete(
        f"/api/v1/shopping/items/{old}", headers=headers(tid)
    )).status_code == 404
    # the host family's list is intact
    listing = await client.get("/api/v1/shopping/items", headers=headers(tid))
    assert [i["id"] for i in listing.json()] == [hitems[0]["id"]]
