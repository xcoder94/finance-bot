"""a-1: GET /api/v1/admin/users — search, keyset pagination, counts, privacy."""

import json
import socket
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models.user import User
from app.models.family_budget import FamilyBudget
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.wallet import Wallet
from tests.admin_helpers import (
    FORBIDDEN_KEY_PARTS,
    make_admin,
    make_user,
    utc,
    walk_keys,
)
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


async def _admin(api_client, monkeypatch):
    client, session = api_client
    admin = await make_user(session, created_at=utc(2020, 1, 1), first_name="adm")
    make_admin(monkeypatch, admin.telegram_id)
    headers = auth_headers(admin.telegram_id)

    async def get(**params):
        resp = await client.get("/api/v1/admin/users", headers=headers, params=params)
        return resp

    return client, session, get


async def test_row_fields_family_and_operation_counts(api_client, monkeypatch) -> None:
    client, session, get = await _admin(api_client, monkeypatch)
    mark = f"mk{uuid.uuid4().hex[:10]}"
    owner = await make_user(
        session,
        created_at=utc(2026, 6, 14, 19, 0, 0),
        first_name=f"{mark} Owner",
        username=f"{mark}_o",
        phone="+998901234567",
        language="uz",
    )
    fam = await session.get(FamilyBudget, owner.family_budget_id)
    fam.name = "SecretFamilyName"
    member = await make_user(
        session, created_at=utc(2026, 6, 15, 1), family=fam, role="member", first_name=f"{mark} M"
    )
    gone = await make_user(
        session, created_at=utc(2026, 6, 15, 2), family=fam, role="member",
        first_name=f"{mark} Gone", is_deleted=True,
    )
    loner = await make_user(session, created_at=utc(2026, 6, 10), first_name=f"{mark} Solo")
    owner.last_seen_at = utc(2026, 6, 15, 8, 30)  # 13:30 Tashkent
    w = Wallet(family_budget_id=fam.id, name="SecretWalletName", currency="UZS")
    cat = IncomeCategory(family_budget_id=fam.id, name="SecretCategory")
    session.add_all([w, cat])
    await session.flush()

    def txn(user, **kw):
        return Transaction(
            family_budget_id=fam.id, type="income", wallet_id=w.id, amount=7654321,
            income_category_id=cat.id, comment="SecretComment", created_by_user_id=user.id,
            transaction_date=datetime.now(UTC), **kw,
        )

    session.add_all(
        [
            txn(owner), txn(owner), txn(owner, is_demo=True),
            txn(owner, is_deleted=True), txn(member),
        ]
    )
    await session.flush()

    resp = await get(q=mark)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 4 - 1  # deleted user not counted
    names = [r["first_name"] for r in data["items"]]
    assert names == [f"{mark} M", f"{mark} Owner", f"{mark} Solo"] or names[0].endswith("M")
    rows = {r["first_name"]: r for r in data["items"]}
    o = rows[f"{mark} Owner"]
    assert o["username"] == f"{mark}_o"
    assert o["phone"] == "+998901234567"
    assert o["language"] == "uz"
    assert o["registered_at"].startswith("2026-06-15T00:00:00") and o["registered_at"].endswith("+05:00")
    assert o["last_seen_at"].startswith("2026-06-15T13:30:00")
    assert o["family_members"] == 2 and o["family_role"] == "owner"
    assert o["operations_count"] == 2
    m = rows[f"{mark} M"]
    assert m["family_role"] == "member" and m["operations_count"] == 1
    assert m["phone"] is None and m["last_seen_at"] is None
    s = rows[f"{mark} Solo"]
    assert s["family_members"] == 1 and s["operations_count"] == 0
    assert "id" in o

    body = json.dumps(data, ensure_ascii=False)
    for key in walk_keys(data):
        assert not any(part in key.lower() for part in FORBIDDEN_KEY_PARTS), key
    for secret in ("7654321", "SecretFamilyName", "SecretWalletName", "SecretCategory", "SecretComment"):
        assert secret not in body


async def test_search_by_name_username_phone_case_insensitive(api_client, monkeypatch) -> None:
    client, session, get = await _admin(api_client, monkeypatch)
    mark = uuid.uuid4().hex[:8]
    a = await make_user(session, first_name=f"Алиса{mark}", created_at=utc(2026, 1, 3))
    b = await make_user(
        session, first_name="Bob", username=f"BobbyX{mark}", created_at=utc(2026, 1, 2)
    )
    c = await make_user(session, first_name="Carl", phone=f"+99890{mark[:0]}7770011", created_at=utc(2026, 1, 1))

    async def ids(q: str) -> set[str]:
        resp = await get(q=q)
        assert resp.status_code == 200, resp.text
        return {r["id"] for r in resp.json()["items"]}

    assert await ids(f"алиса{mark}") == {str(a.id)}  # case-insensitive part of name
    assert await ids(f"ИСА{mark}") == {str(a.id)}
    assert await ids(f"bobbyx{mark}") == {str(b.id)}
    assert await ids(f"@BOBBYX{mark}") == {str(b.id)}
    assert await ids("7770011") == {str(c.id)}
    assert await ids("+998 90 777-00-11") == {str(c.id)}
    assert await ids(f"nomatch{mark}") == set()
    assert (await get(q=f"nomatch{mark}")).json() == {"items": [], "total": 0, "next_cursor": None}


async def test_wildcards_in_q_are_literal(api_client, monkeypatch) -> None:
    client, session, get = await _admin(api_client, monkeypatch)
    mark = uuid.uuid4().hex[:8]
    pct = await make_user(session, first_name=f"{mark}100%_x")
    plain = await make_user(session, first_name=f"{mark}100abx")
    resp = await get(q=f"{mark}100%")
    assert {r["id"] for r in resp.json()["items"]} == {str(pct.id)}
    resp = await get(q=f"{mark}100_")
    assert {r["id"] for r in resp.json()["items"]} == set()
    resp = await get(q=f"{mark}100\\")
    assert resp.status_code == 200 and resp.json()["items"] == []
    assert plain  # silence unused


async def test_pagination_no_duplicates_no_gaps_with_equal_timestamps(api_client, monkeypatch) -> None:
    client, session, get = await _admin(api_client, monkeypatch)
    mark = f"pg{uuid.uuid4().hex[:8]}"
    same = utc(2026, 3, 1, 12)
    created = []
    for i in range(7):  # 7 users share one created_at: order must rely on id tie-break
        created.append(await make_user(session, first_name=f"{mark}-{i}", created_at=same))
    for i in range(3):
        created.append(await make_user(session, first_name=f"{mark}-n{i}", created_at=utc(2026, 4, 1 + i)))
    expected = {str(u.id) for u in created}

    seen: list[str] = []
    cursor = None
    pages = 0
    while True:
        params = {"q": mark, "limit": 3}
        if cursor:
            params["cursor"] = cursor
        data = (await get(**params)).json()
        assert data["total"] == 10
        assert len(data["items"]) <= 3
        seen += [r["id"] for r in data["items"]]
        pages += 1
        cursor = data["next_cursor"]
        if cursor is None:
            break
        assert pages < 10
    assert pages == 4
    assert len(seen) == len(set(seen)) == 10
    assert set(seen) == expected
    # newest first: the three April users lead, newest of them first
    assert seen[:3] == [str(created[9].id), str(created[8].id), str(created[7].id)]


async def test_default_and_limit_validation(api_client, monkeypatch) -> None:
    client, session, get = await _admin(api_client, monkeypatch)
    mark = f"dl{uuid.uuid4().hex[:8]}"
    for i in range(55):
        await make_user(session, first_name=f"{mark}{i}", created_at=utc(2026, 2, 1, 0, i))
    data = (await get(q=mark)).json()
    assert len(data["items"]) == 50 and data["total"] == 55 and data["next_cursor"]
    assert len((await get(q=mark, limit=100)).json()["items"]) == 55
    assert (await get(limit=101)).status_code == 422
    assert (await get(limit=0)).status_code == 422
    assert (await get(q="x" * 65)).status_code == 422
    assert (await get(q="x" * 64)).status_code == 200
    assert (await get(cursor="not-a-cursor")).status_code == 422


async def test_admin_endpoints_are_read_only(api_client, monkeypatch) -> None:
    client, session, get = await _admin(api_client, monkeypatch)
    admin_headers = auth_headers(
        (await session.execute(select(User.telegram_id).where(User.first_name == "adm"))).scalars().first()
    )
    for path in ("/api/v1/admin/users", "/api/v1/admin/overview"):
        for method in ("post", "put", "patch", "delete"):
            resp = await getattr(client, method)(path, headers=admin_headers)
            assert resp.status_code == 405, (method, path)
