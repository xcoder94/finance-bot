"""dev-fix12: history order (Tashkent day, created_at, id) and wallet_id filter."""

import socket
import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from tests.db_helpers import db_address
from tests.test_wallets_categories import (
    api_client,  # noqa: F401
    auth_headers,
    create_user_with_budget,
)

TZ5 = timezone(timedelta(hours=5))
URL = "/api/v1/transactions/history"
RANGE = {
    "date_from": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
    "date_to": datetime(2026, 12, 31, tzinfo=UTC).isoformat(),
}


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


def _tid() -> int:
    return int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000


def _uid(n: int) -> uuid.UUID:
    return uuid.UUID(int=n)


async def _base(session: AsyncSession):
    tid = _tid()
    user, budget = await create_user_with_budget(session, telegram_id=tid)
    wallet = Wallet(family_budget_id=budget.id, name="W", currency="UZS")
    cat = IncomeCategory(family_budget_id=budget.id, name="Sal")
    session.add_all([wallet, cat])
    await session.flush()
    return tid, user, budget, wallet, cat


def _income(budget, user, wallet, cat, amount, when, created, id_=None):
    kw = {}
    if id_ is not None:
        kw["id"] = id_
    return Transaction(
        family_budget_id=budget.id,
        type="income",
        wallet_id=wallet.id,
        amount=amount,
        income_category_id=cat.id,
        created_by_user_id=user.id,
        transaction_date=when,
        created_at=created,
        **kw,
    )


async def _get(client, tid, **extra):
    resp = await client.get(URL, headers=auth_headers(tid), params={**RANGE, **extra})
    return resp


async def test_same_day_newest_created_first_not_by_id(api_client) -> None:
    client, session = api_client
    tid, user, budget, wallet, cat = await _base(session)
    noon = datetime(2026, 3, 10, 12, 0, tzinfo=TZ5)
    base = datetime(2026, 3, 10, 8, 0, tzinfo=UTC)
    # amount k created at base+k; ids chosen so id DESC would give 1,3,2,4... order
    ids = {1: 90, 2: 10, 3: 70, 4: 30}
    session.add_all(
        _income(budget, user, wallet, cat, k, noon, base + timedelta(minutes=k), _uid(ids[k]))
        for k in ids
    )
    await session.flush()
    resp = await _get(client, tid)
    assert resp.status_code == 200
    assert [i["amount"] for i in resp.json()["items"]] == [4, 3, 2, 1]


async def test_yesterday_entered_later_sits_below_today_above_other_yesterday(api_client) -> None:
    client, session = api_client
    tid, user, budget, wallet, cat = await _base(session)
    today = datetime(2026, 3, 10, 12, 0, tzinfo=TZ5)
    yest = datetime(2026, 3, 9, 12, 0, tzinfo=TZ5)
    t0 = datetime(2026, 3, 8, 0, 0, tzinfo=UTC)
    session.add_all(
        [
            _income(budget, user, wallet, cat, 1, yest, t0 + timedelta(hours=1)),
            _income(budget, user, wallet, cat, 2, today, t0 + timedelta(hours=2)),
            _income(budget, user, wallet, cat, 3, yest, t0 + timedelta(hours=9)),  # entered last
            _income(budget, user, wallet, cat, 4, today, t0 + timedelta(hours=3)),
        ]
    )
    await session.flush()
    resp = await _get(client, tid)
    assert [i["amount"] for i in resp.json()["items"]] == [4, 2, 3, 1]


async def test_tashkent_day_boundary(api_client) -> None:
    client, session = api_client
    tid, user, budget, wallet, cat = await _base(session)
    # 00:30 +05:00 of day N = 19:30 UTC of N-1 ; 23:00 +05:00 of N-1 = 18:00 UTC of N-1: same UTC date
    day_n = datetime(2026, 3, 10, 0, 30, tzinfo=TZ5)
    day_prev = datetime(2026, 3, 9, 23, 0, tzinfo=TZ5)
    assert day_n.astimezone(UTC).date() == day_prev.astimezone(UTC).date()
    t0 = datetime(2026, 3, 1, tzinfo=UTC)
    session.add_all(
        [
            _income(budget, user, wallet, cat, 1, day_n, t0),
            _income(budget, user, wallet, cat, 2, day_prev, t0 + timedelta(hours=5)),
        ]
    )
    await session.flush()
    resp = await _get(client, tid)
    assert [i["amount"] for i in resp.json()["items"]] == [1, 2]


async def test_pages_stable_with_equal_created_at(api_client) -> None:
    client, session = api_client
    tid, user, budget, wallet, cat = await _base(session)
    noon = datetime(2026, 3, 10, 12, 0, tzinfo=TZ5)
    same = datetime(2026, 3, 10, 9, 0, tzinfo=UTC)
    session.add_all(
        _income(budget, user, wallet, cat, k, noon, same, _uid(100 - k)) for k in range(1, 8)
    )
    await session.flush()
    full = [i["id"] for i in (await _get(client, tid, limit=50)).json()["items"]]
    assert len(full) == 7
    paged: list[str] = []
    for off in range(0, 7, 2):
        paged += [i["id"] for i in (await _get(client, tid, limit=2, offset=off)).json()["items"]]
    assert paged == full
    assert len(set(paged)) == 7


async def test_amount_edit_keeps_place_date_edit_moves(api_client) -> None:
    client, session = api_client
    tid, user, budget, wallet, cat = await _base(session)
    d1 = datetime(2026, 3, 10, 12, 0, tzinfo=TZ5)
    d2 = datetime(2026, 3, 11, 12, 0, tzinfo=TZ5)
    t0 = datetime(2026, 3, 1, tzinfo=UTC)
    older = _income(budget, user, wallet, cat, 1, d1, t0)
    newer = _income(budget, user, wallet, cat, 2, d1, t0 + timedelta(hours=1))
    session.add_all([older, newer])
    await session.flush()
    def full(amount, when):
        return {
            "amount": amount,
            "transaction_date": when.isoformat(),
            "wallet_id": str(wallet.id),
            "income_category_id": str(cat.id),
        }

    r = await client.patch(
        f"/api/v1/transactions/{older.id}", headers=auth_headers(tid), json=full(999, d1)
    )
    assert r.status_code == 200, r.text
    items = (await _get(client, tid)).json()["items"]
    assert [i["amount"] for i in items] == [2, 999]
    r = await client.patch(
        f"/api/v1/transactions/{older.id}",
        headers=auth_headers(tid),
        json=full(999, d2),
    )
    assert r.status_code == 200, r.text
    items = (await _get(client, tid)).json()["items"]
    assert [i["amount"] for i in items] == [999, 2]


# ---------------- wallet_id filter ----------------


async def _two_wallets(session):
    tid, user, budget, w1, cat = await _base(session)
    w2 = Wallet(family_budget_id=budget.id, name="W2", currency="UZS")
    w3 = Wallet(family_budget_id=budget.id, name="W3", currency="UZS")
    exp = ExpenseCategory(family_budget_id=budget.id, name="Food")
    session.add_all([w2, w3, exp])
    await session.flush()
    sub = ExpenseCategory(family_budget_id=budget.id, name="Sub", parent_id=exp.id)
    session.add(sub)
    await session.flush()
    return tid, user, budget, w1, w2, w3, cat, sub


def _dt(h=12):
    return datetime(2026, 3, 10, h, 0, tzinfo=TZ5)


def _expense(budget, user, wallet, sub, amount):
    return Transaction(
        family_budget_id=budget.id, type="expense", wallet_id=wallet.id, amount=amount,
        expense_category_id=sub.id, created_by_user_id=user.id, transaction_date=_dt(),
    )


def _transfer(budget, user, src, dst, amount):
    return Transaction(
        family_budget_id=budget.id, type="transfer", wallet_id=src.id, to_wallet_id=dst.id,
        amount=amount, to_amount=amount, created_by_user_id=user.id, transaction_date=_dt(),
    )


async def test_wallet_filter_returns_own_ops_only(api_client) -> None:
    client, session = api_client
    tid, user, budget, w1, w2, w3, cat, sub = await _two_wallets(session)
    session.add_all(
        [
            _income(budget, user, w1, cat, 1, _dt(), datetime(2026, 3, 1, tzinfo=UTC)),
            _expense(budget, user, w1, sub, 2),
            _transfer(budget, user, w1, w2, 3),  # outgoing for w1
            _transfer(budget, user, w3, w1, 4),  # incoming for w1
            _income(budget, user, w2, cat, 50, _dt(), datetime(2026, 3, 1, tzinfo=UTC)),
            _expense(budget, user, w3, sub, 60),
            _transfer(budget, user, w2, w3, 70),
        ]
    )
    await session.flush()
    body = (await _get(client, tid, wallet_id=str(w1.id))).json()
    assert sorted(i["amount"] for i in body["items"]) == [1, 2, 3, 4]
    assert body["total_count"] == 4
    all_body = (await _get(client, tid)).json()
    assert all_body["total_count"] == 7


async def test_wallet_filter_404_cases(api_client) -> None:
    client, session = api_client
    tid, user, budget, w1, cat = await _base(session)
    other_tid = _tid()
    other, other_budget = await create_user_with_budget(session, telegram_id=other_tid)
    foreign = Wallet(family_budget_id=other_budget.id, name="F", currency="UZS")
    deleted = Wallet(
        family_budget_id=budget.id, name="D", currency="UZS",
        is_deleted=True, deleted_at=datetime.now(UTC),
    )
    member = User(telegram_id=_tid(), family_budget_id=budget.id, role="member", language="ru")
    session.add_all([foreign, deleted, member])
    await session.flush()
    foreign_personal = Wallet(
        family_budget_id=budget.id, name="P", currency="UZS",
        is_personal=True, owner_user_id=member.id,
    )
    session.add(foreign_personal)
    await session.flush()
    for wid in (foreign.id, foreign_personal.id, deleted.id, uuid.uuid4()):
        resp = await _get(client, tid, wallet_id=str(wid))
        assert resp.status_code == 404, (wid, resp.text)
        assert "items" not in resp.json()


async def test_wallet_filter_own_personal_ok(api_client) -> None:
    client, session = api_client
    tid, user, budget, w1, cat = await _base(session)
    mine = Wallet(
        family_budget_id=budget.id, name="Mine", currency="UZS",
        is_personal=True, owner_user_id=user.id,
    )
    session.add(mine)
    await session.flush()
    session.add(_income(budget, user, mine, cat, 5, _dt(), datetime(2026, 3, 1, tzinfo=UTC)))
    await session.flush()
    resp = await _get(client, tid, wallet_id=str(mine.id))
    assert resp.status_code == 200
    assert [i["amount"] for i in resp.json()["items"]] == [5]


async def test_wallet_filter_hides_transfer_to_foreign_personal(api_client) -> None:
    client, session = api_client
    tid, user, budget, shared, cat = await _base(session)
    member_tid = _tid()
    member = User(telegram_id=member_tid, family_budget_id=budget.id, role="member", language="ru")
    session.add(member)
    await session.flush()
    mpers = Wallet(
        family_budget_id=budget.id, name="MP", currency="UZS",
        is_personal=True, owner_user_id=member.id,
    )
    session.add(mpers)
    await session.flush()
    session.add_all(
        [
            _transfer(budget, member, shared, mpers, 11),  # shared -> member's personal
            _income(budget, user, shared, cat, 12, _dt(), datetime(2026, 3, 1, tzinfo=UTC)),
        ]
    )
    await session.flush()
    # the owner (not the personal wallet's owner) must not see the transfer
    body = (await _get(client, tid, wallet_id=str(shared.id))).json()
    assert [i["amount"] for i in body["items"]] == [12]
    assert body["total_count"] == 1
    # the member sees both
    body = (await _get(client, member_tid, wallet_id=str(shared.id))).json()
    assert sorted(i["amount"] for i in body["items"]) == [11, 12]
    assert body["total_count"] == 2


async def test_wallet_filter_combines_with_category_and_default_unchanged(api_client) -> None:
    client, session = api_client
    tid, user, budget, w1, w2, w3, cat, sub = await _two_wallets(session)
    session.add_all(
        [
            _expense(budget, user, w1, sub, 1),
            _expense(budget, user, w2, sub, 2),
            _income(budget, user, w1, cat, 3, _dt(), datetime(2026, 3, 1, tzinfo=UTC)),
        ]
    )
    await session.flush()
    body = (
        await _get(client, tid, wallet_id=str(w1.id), expense_category_id=str(sub.id))
    ).json()
    assert [i["amount"] for i in body["items"]] == [1]
    assert body["total_count"] == 1
    assert (await _get(client, tid)).json()["total_count"] == 3
