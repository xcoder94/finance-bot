"""QA (m3-3): extra edge cases / races for the shopping API on real Postgres.

Reuses the developer fixtures from tests/test_shopping.py.
"""

import asyncio
import uuid

import pytest
from sqlalchemy import func, select

from app.db import async_session_factory
from app.models.shopping import ShoppingItem, ShoppingPurchase
from app.models.transaction import Transaction
from tests.test_shopping import (  # noqa: F401  (fixtures)
    add_items,
    api_client,
    buy,
    committed_family,
    headers,
    make_family,
    real_client,
)

pytestmark = [pytest.mark.anyio]




@pytest.mark.parametrize("bad", ["мол\x00око", "\x00"])
async def test_nul_char_in_name_is_rejected_not_500(api_client, bad) -> None:
    client, session = api_client
    fam = await make_family(session)
    r = await client.post(
        "/api/v1/shopping/items", headers=headers(fam["user"].telegram_id), json={"name": bad}
    )
    assert r.status_code == 422, (r.status_code, r.text)


async def test_nul_char_in_rename_is_rejected_not_500(api_client) -> None:
    client, session = api_client
    fam = await make_family(session)
    tid = fam["user"].telegram_id
    (a,) = await add_items(client, tid, "хлеб")
    r = await client.patch(
        f"/api/v1/shopping/items/{a['id']}", headers=headers(tid), json={"name": "x\x00y"}
    )
    assert r.status_code == 422, (r.status_code, r.text)


@pytest.mark.parametrize("bad", [
    pytest.param(True, marks=pytest.mark.xfail(strict=True, reason="pydantic lax int: true -> 1 (same as ExpenseCreate)")),
    412000.5, "abc", None, -1, 0])
async def test_amount_bad_types(api_client, bad) -> None:
    client, session = api_client
    fam = await make_family(session)
    tid = fam["user"].telegram_id
    (a,) = await add_items(client, tid, "хлеб")
    r = await client.post(
        "/api/v1/shopping/purchases", headers=headers(tid),
        json={"item_ids": [a["id"]], "amount": bad, "client_token": str(uuid.uuid4())},
    )
    assert r.status_code == 422, (bad, r.status_code, r.text)
    assert await session.scalar(select(func.count()).select_from(Transaction)) == 0


async def test_replay_same_token_other_payload_creates_nothing(api_client) -> None:
    client, session = api_client
    fam = await make_family(session)
    tid = fam["user"].telegram_id
    a, b = await add_items(client, tid, "хлеб", "сыр")
    tok = uuid.uuid4()
    r1 = await buy(client, tid, [a["id"]], amount=1000, token=tok)
    r2 = await buy(client, tid, [b["id"]], amount=9999, token=tok)
    assert (r1.status_code, r2.status_code) == (201, 200)
    assert r2.json()["amount"] == 1000
    assert await session.scalar(select(func.count()).select_from(Transaction)) == 1
    names = [i["name"] for i in (await client.get("/api/v1/shopping/items", headers=headers(tid))).json()]
    assert names == ["сыр"]


async def test_other_member_cannot_replay_my_token(api_client) -> None:
    """The token is per user: B reusing A's token gets an own purchase, not A's result."""
    client, session = api_client
    fam = await make_family(session, second_member=True)
    a_tid, b_tid = fam["user"].telegram_id, fam["other"].telegram_id
    x, y = await add_items(client, a_tid, "хлеб", "сыр")
    tok = uuid.uuid4()
    r1 = await buy(client, a_tid, [x["id"]], amount=1000, token=tok)
    r2 = await buy(client, b_tid, [y["id"]], amount=2000, token=tok)
    assert (r1.status_code, r2.status_code) == (201, 201), r2.text
    assert r2.json()["id"] != r1.json()["id"] and r2.json()["amount"] == 2000


async def test_purchase_comment_is_names_in_list_order(api_client) -> None:
    client, session = api_client
    fam = await make_family(session)
    tid = fam["user"].telegram_id
    a, b, c = await add_items(client, tid, "молоко", "хлеб", "сыр")
    res = (await buy(client, tid, [c["id"], a["id"]], amount=412_000)).json()
    tx = await session.get(Transaction, uuid.UUID(res["transaction_id"]))
    assert tx.comment == "сыр, молоко"  # request order (the client sends list order)
    assert tx.type == "expense" and tx.amount == 412_000
    assert res["category_label"] == "Еда · Продукты" and res["items_left"] == 1


class TestQaRaces:
    async def test_limit_race_two_members_at_99(self, committed_family, real_client) -> None:
        fam = committed_family
        async with async_session_factory() as s:
            for i in range(99):
                s.add(ShoppingItem(family_budget_id=fam["budget_id"], name=f"p{i}",
                                   added_by_user_id=fam["user_id"]))
            await s.commit()
        rs = await asyncio.gather(*[
            real_client.post("/api/v1/shopping/items",
                             headers=headers(fam["tid"] if i % 2 else fam["other_tid"]),
                             json={"name": f"new{i}"})
            for i in range(6)
        ])
        codes = sorted(r.status_code for r in rs)
        assert codes == [201, 409, 409, 409, 409, 409], [r.text for r in rs]
        async with async_session_factory() as s:
            assert await s.scalar(select(func.count()).select_from(ShoppingItem).where(
                ShoppingItem.family_budget_id == fam["budget_id"])) == 100

    async def test_purchase_vs_delete_race(self, committed_family, real_client) -> None:
        fam = committed_family
        (a,) = await add_items(real_client, fam["tid"], "хлеб")
        rp, rd = await asyncio.gather(
            buy(real_client, fam["tid"], [a["id"]], amount=5000),
            real_client.delete(f"/api/v1/shopping/items/{a['id']}", headers=headers(fam["other_tid"])),
        )
        # delete first: the item is not the family's any more -> 404 and nothing recorded
        # (ux-next3b); buy first: 201 and one expense. Never an expense without a purchase.
        assert rp.status_code in (201, 404), rp.text
        assert rd.status_code in (204, 404), rd.text
        want = 1 if rp.status_code == 201 else 0
        async with async_session_factory() as s:
            assert await s.scalar(select(func.count()).select_from(Transaction).where(
                Transaction.family_budget_id == fam["budget_id"])) == want
            assert await s.scalar(select(func.count()).select_from(ShoppingPurchase).where(
                ShoppingPurchase.family_budget_id == fam["budget_id"])) == want

    async def test_ten_parallel_replays_one_expense(self, committed_family, real_client) -> None:
        fam = committed_family
        items = await add_items(real_client, fam["tid"], "a", "b")
        tok = uuid.uuid4()
        rs = await asyncio.gather(*[
            buy(real_client, fam["tid"], [i["id"] for i in items], amount=7000, token=tok)
            for _ in range(10)
        ])
        assert sorted(r.status_code for r in rs) == [200] * 9 + [201]
        assert len({r.json()["transaction_id"] for r in rs}) == 1


async def test_no_default_wallet_skips_own_older_personal_wallet(api_client) -> None:
    """Fallback = oldest SHARED wallet, even when the user's personal wallet is older."""
    from datetime import timedelta

    from app.models.wallet import Wallet

    client, session = api_client
    fam = await make_family(session, default_wallet=False)
    personal = Wallet(
        family_budget_id=fam["budget"].id, name="Мой личный", currency="UZS",
        is_personal=True, owner_user_id=fam["user"].id,
        created_at=fam["wallet"].created_at - timedelta(days=1),
    )
    session.add(personal)
    await session.flush()
    tid = fam["user"].telegram_id
    (a,) = await add_items(client, tid, "хлеб")
    res = (await buy(client, tid, [a["id"]], amount=1000)).json()
    assert res["wallet_name"] == "Карта сум"


@pytest.mark.parametrize("bad", ["мол\x00око", "\x00", "a\x1bb", "a\ud800b"])
def test_normalize_item_name_rejects_control_chars(bad) -> None:
    # add_shopping_items (bot path) turns this ValueError into `invalid`.
    from app.schemas.shopping import normalize_item_name

    with pytest.raises(ValueError):
        normalize_item_name(bad)
