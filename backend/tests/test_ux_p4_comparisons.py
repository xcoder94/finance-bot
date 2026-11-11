"""UX P4: previous-period amounts, expense comparison, income shares, parent history filter."""

import uuid
from datetime import UTC, datetime, timedelta, timezone

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.wallet import Wallet
from app.services.history_analytics import resolve_previous_period
from tests.test_history_analytics import (  # noqa: F401
    api_client,
    auth_headers,
    create_user_with_budget,
    pytestmark,
)

TZ = timezone(timedelta(hours=5))
NOV = {
    "date_from": datetime(2026, 11, 1, tzinfo=TZ).isoformat(),
    "date_to": datetime(2026, 11, 30, 23, 59, 59, 999000, tzinfo=TZ).isoformat(),
}
OCT_DATE = datetime(2026, 10, 15, 12, tzinfo=TZ)
NOV_DATE = datetime(2026, 11, 15, 12, tzinfo=TZ)


def _tg() -> int:
    return int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000


def _txn(budget, user, wallet, cat, amount, date, *, kind="expense", deleted=False):
    kwargs = (
        {"expense_category_id": cat.id if cat else None}
        if kind == "expense"
        else {"income_category_id": cat.id}
    )
    return Transaction(
        family_budget_id=budget.id,
        type=kind,
        wallet_id=wallet.id,
        amount=amount,
        created_by_user_id=user.id,
        transaction_date=date,
        is_deleted=deleted,
        **kwargs,
    )


async def _seed(session: AsyncSession, tg: int):
    user, budget = await create_user_with_budget(session, telegram_id=tg)
    wallet = Wallet(family_budget_id=budget.id, name="W", currency="UZS")
    usd = Wallet(family_budget_id=budget.id, name="USD", currency="USD")
    personal = Wallet(
        family_budget_id=budget.id, name="Mine", currency="UZS",
        is_personal=True, owner_user_id=user.id,
    )
    food = ExpenseCategory(family_budget_id=budget.id, name="Food")
    taxi = ExpenseCategory(family_budget_id=budget.id, name="Taxi")
    fun = ExpenseCategory(family_budget_id=budget.id, name="Fun")
    session.add_all([wallet, usd, personal, food, taxi, fun])
    await session.flush()
    groceries = ExpenseCategory(family_budget_id=budget.id, name="Groceries", parent_id=food.id)
    old_sub = ExpenseCategory(
        family_budget_id=budget.id, name="Old", parent_id=food.id, is_deleted=True
    )
    session.add_all([groceries, old_sub])
    await session.flush()
    add = session.add_all
    add([
        # October total 1_000_000: Food(own 100k + groceries 400k), Taxi 500k
        _txn(budget, user, wallet, food, 100_000, OCT_DATE),
        _txn(budget, user, wallet, groceries, 400_000, OCT_DATE),
        _txn(budget, user, wallet, taxi, 500_000, OCT_DATE),
        # noise in October: personal, USD, deleted tx must not count
        _txn(budget, user, personal, taxi, 77_000, OCT_DATE),
        _txn(budget, user, usd, taxi, 55, OCT_DATE),
        _txn(budget, user, wallet, taxi, 9_999, OCT_DATE, deleted=True),
        # November total 1_120_000: Food 620k (groceries 600k + own 20k), Taxi 400k, Fun 100k (new)
        _txn(budget, user, wallet, groceries, 600_000, NOV_DATE),
        _txn(budget, user, wallet, food, 20_000, NOV_DATE),
        _txn(budget, user, wallet, taxi, 400_000, NOV_DATE),
        _txn(budget, user, wallet, fun, 100_000, NOV_DATE),
        # uncategorized
        _txn(budget, user, wallet, None, 30_000, OCT_DATE),
        _txn(budget, user, wallet, None, 0 + 45_000, NOV_DATE),
    ])
    await session.flush()
    return user, budget, food, groceries, old_sub, taxi, fun


async def test_expenses_by_category_has_prev_amount(api_client):
    client, session = api_client
    tg = _tg()
    _, _, food, _, _, taxi, fun = await _seed(session, tg)
    resp = await client.get(
        "/api/v1/analytics/expenses-by-category",
        headers=auth_headers(tg),
        params={"currency": "UZS", **NOV},
    )
    assert resp.status_code == 200
    rows = {r["category_name"]: r for r in resp.json()}
    assert rows["Food"]["amount"] == 620_000 and rows["Food"]["prev_amount"] == 500_000
    assert rows["Taxi"]["amount"] == 400_000 and rows["Taxi"]["prev_amount"] == 500_000
    assert rows["Fun"]["amount"] == 100_000 and rows["Fun"]["prev_amount"] == 0
    unc = [r for r in resp.json() if r["uncategorized"]][0]
    assert unc["amount"] == 45_000 and unc["prev_amount"] == 30_000


async def test_expenses_by_subcategory_has_prev_amount(api_client):
    client, session = api_client
    tg = _tg()
    _, _, food, groceries, _, _, _ = await _seed(session, tg)
    resp = await client.get(
        "/api/v1/analytics/expenses-by-subcategory",
        headers=auth_headers(tg),
        params={"currency": "UZS", "parent_category_id": str(food.id), **NOV},
    )
    assert resp.status_code == 200
    rows = {r["subcategory_id"]: r for r in resp.json()}
    assert rows[str(groceries.id)]["prev_amount"] == 400_000
    assert rows[str(food.id)]["prev_amount"] == 100_000


async def test_expense_comparison_totals(api_client):
    client, session = api_client
    tg = _tg()
    await _seed(session, tg)
    resp = await client.get(
        "/api/v1/analytics/expense-comparison",
        headers=auth_headers(tg),
        params={"currency": "UZS", **NOV},
    )
    assert resp.status_code == 200
    body = resp.json()
    # categorized + uncategorized
    assert body["total"] == 1_120_000 + 45_000
    assert body["prev_total"] == 1_000_000 + 30_000
    assert body["prev_date_from"].startswith("2026-10-01T00:00:00")  # Oct 1 Tashkent
    assert body["prev_date_to"].startswith("2026-10-31T23:59:59.999999")


async def test_expense_comparison_empty_prev_is_zero(api_client):
    client, session = api_client
    tg = _tg()
    await create_user_with_budget(session, telegram_id=tg)
    resp = await client.get(
        "/api/v1/analytics/expense-comparison",
        headers=auth_headers(tg),
        params={"currency": "UZS", **NOV},
    )
    assert resp.json()["total"] == 0 and resp.json()["prev_total"] == 0


async def test_custom_30_day_range_compares_previous_30_days(api_client):
    client, session = api_client
    tg = _tg()
    user, budget = await create_user_with_budget(session, telegram_id=tg)
    w = Wallet(family_budget_id=budget.id, name="W", currency="UZS")
    c = ExpenseCategory(family_budget_id=budget.id, name="C")
    session.add_all([w, c])
    await session.flush()
    start = datetime(2026, 11, 5, tzinfo=TZ)  # Nov 5 .. Dec 4 (30 days)
    session.add_all([
        _txn(budget, user, w, c, 10, start + timedelta(days=3)),
        _txn(budget, user, w, c, 7, start - timedelta(days=1)),    # Nov 4: prev
        _txn(budget, user, w, c, 5, start - timedelta(days=30)),   # Oct 6 00:00: prev, first instant
        _txn(budget, user, w, c, 900, start - timedelta(days=31)), # Oct 5: outside
    ])
    await session.flush()
    params = {
        "currency": "UZS",
        "date_from": start.isoformat(),
        "date_to": datetime(2026, 12, 4, 23, 59, 59, 999000, tzinfo=TZ).isoformat(),
    }
    resp = await client.get(
        "/api/v1/analytics/expense-comparison", headers=auth_headers(tg), params=params
    )
    assert resp.json()["total"] == 10
    assert resp.json()["prev_total"] == 12
    rows = (
        await client.get(
            "/api/v1/analytics/expenses-by-category", headers=auth_headers(tg), params=params
        )
    ).json()
    assert rows[0]["amount"] == 10 and rows[0]["prev_amount"] == 12


def test_resolve_previous_period_calendar_month_and_custom():
    f = datetime(2026, 3, 1, tzinfo=TZ)
    t = datetime(2026, 3, 31, 23, 59, 59, 999000, tzinfo=TZ)
    pf, pt = resolve_previous_period(f, t)
    assert pf == datetime(2026, 2, 1, tzinfo=TZ)
    assert pt.astimezone(TZ).date().isoformat() == "2026-02-28"
    assert pt.astimezone(TZ).hour == 23
    # January -> December of previous year
    pf, pt = resolve_previous_period(
        datetime(2026, 1, 1, tzinfo=TZ), datetime(2026, 1, 31, 23, 59, 59, 999000, tzinfo=TZ)
    )
    assert pf == datetime(2025, 12, 1, tzinfo=TZ)
    # custom 7 days
    f = datetime(2026, 3, 10, tzinfo=TZ)
    t = datetime(2026, 3, 16, 23, 59, 59, 999000, tzinfo=TZ)
    pf, pt = resolve_previous_period(f, t)
    assert pf == datetime(2026, 3, 3, tzinfo=TZ)
    assert pt < f and f - pt < timedelta(milliseconds=2)


async def test_income_by_category_shares_and_prev(api_client):
    client, session = api_client
    tg = _tg()
    user, budget = await create_user_with_budget(session, telegram_id=tg)
    w = Wallet(family_budget_id=budget.id, name="W", currency="UZS")
    p = Wallet(
        family_budget_id=budget.id, name="Mine", currency="UZS",
        is_personal=True, owner_user_id=user.id,
    )
    salary = IncomeCategory(family_budget_id=budget.id, name="Salary")
    gift = IncomeCategory(family_budget_id=budget.id, name="Gift")
    session.add_all([w, p, salary, gift])
    await session.flush()
    session.add_all([
        _txn(budget, user, w, salary, 750, NOV_DATE, kind="income"),
        _txn(budget, user, w, gift, 250, NOV_DATE, kind="income"),
        _txn(budget, user, p, gift, 5000, NOV_DATE, kind="income"),
        _txn(budget, user, w, salary, 600, OCT_DATE, kind="income"),
    ])
    await session.flush()
    resp = await client.get(
        "/api/v1/analytics/income-by-category",
        headers=auth_headers(tg),
        params={"currency": "UZS", **NOV},
    )
    rows = {r["category_name"]: r for r in resp.json()}
    assert rows["Salary"]["share_percent"] == 75.0
    assert rows["Gift"]["share_percent"] == 25.0
    assert rows["Salary"]["prev_amount"] == 600 and rows["Gift"]["prev_amount"] == 0


async def test_history_parent_filter_includes_subcategories_and_deleted(api_client):
    client, session = api_client
    tg = _tg()
    _, budget, food, groceries, old_sub, taxi, _ = await _seed(session, tg)
    # a transaction on the soft-deleted subcategory
    from sqlalchemy import select
    from app.models.user import User
    user = (await session.execute(select(User).where(User.telegram_id == tg))).scalar_one()
    w = (await session.execute(
        select(Wallet).where(Wallet.family_budget_id == budget.id, Wallet.name == "W")
    )).scalar_one()
    session.add(_txn(budget, user, w, old_sub, 1234, NOV_DATE))
    await session.flush()

    async def amounts(cat_id):
        resp = await client.get(
            "/api/v1/transactions/history",
            headers=auth_headers(tg),
            params={**NOV, "expense_category_id": str(cat_id), "limit": 100},
        )
        assert resp.status_code == 200
        return sorted(i["amount"] for i in resp.json()["items"])

    assert await amounts(food.id) == sorted([600_000, 20_000, 1234])
    # filtering by a subcategory still returns only that subcategory
    assert await amounts(groceries.id) == [600_000]
    assert await amounts(taxi.id) == [400_000]


def test_resolve_previous_period_october_gives_september_dates():
    # r2 #8: a whole 31-day month is compared with the real previous month (30 days);
    # prev_date_from/prev_date_to carry the honest bounds, the label is the client's job.
    pf, pt = resolve_previous_period(
        datetime(2026, 10, 1, tzinfo=TZ), datetime(2026, 10, 31, 23, 59, 59, 999000, tzinfo=TZ)
    )
    assert pf == datetime(2026, 9, 1, tzinfo=TZ)
    assert pt.astimezone(TZ).date().isoformat() == "2026-09-30"
    assert (pt.astimezone(TZ).date() - pf.astimezone(TZ).date()).days + 1 == 30


def test_resolve_previous_period_none_at_calendar_edge():
    lo = datetime(1, 1, 1, tzinfo=UTC)
    hi = datetime(9999, 12, 31, 23, 59, 59, tzinfo=UTC)
    assert resolve_previous_period(lo, lo + timedelta(days=1)) is None


async def test_far_dates_do_not_500(api_client):
    client, session = api_client
    tg = _tg()
    _, _, food, _, _, _, _ = await _seed(session, tg)
    far = {"date_from": "0001-01-01T00:00:00+00:00", "date_to": "9999-12-31T23:59:59+00:00"}
    ranges = [far, {**far, "date_to": NOV["date_to"]}, {**far, "date_from": NOV["date_from"]}]
    for rng in ranges:
        for path, extra in [
            ("expenses-by-category", {}),
            ("income-by-category", {}),
            ("expenses-by-subcategory", {"parent_category_id": str(food.id)}),
            ("expense-comparison", {}),
        ]:
            resp = await client.get(
                f"/api/v1/analytics/{path}",
                headers=auth_headers(tg),
                params={"currency": "UZS", **extra, **rng},
            )
            assert resp.status_code == 200, (path, rng, resp.text)
    resp = await client.get(
        "/api/v1/analytics/expense-comparison",
        headers=auth_headers(tg),
        params={"currency": "UZS", **far},
    )
    body = resp.json()
    assert body["prev_total"] == 0 and body["prev_date_from"] is None
    assert body["total"] > 0
