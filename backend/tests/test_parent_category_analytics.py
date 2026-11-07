"""Expenses booked directly on a parent category must appear in category analytics."""

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from app.models.transaction import Transaction
from app.models.wallet import Wallet
from tests.test_history_analytics import (  # noqa: F401
    api_client,
    auth_headers,
    create_user_with_budget,
    pytestmark,
)
from tests.test_phase5_analytics import (
    SELECTED_MONTH_DATE,
    SELECTED_MONTH_END,
    SELECTED_MONTH_START,
)

PARAMS = {
    "currency": "UZS",
    "date_from": SELECTED_MONTH_START.isoformat(),
    "date_to": SELECTED_MONTH_END.isoformat(),
}


async def _seed(session: AsyncSession, budget, user):
    wallet = Wallet(family_budget_id=budget.id, name="W", currency="UZS")
    qarz = ExpenseCategory(family_budget_id=budget.id, name="Qarz")
    food = ExpenseCategory(family_budget_id=budget.id, name="Food")
    session.add_all([wallet, qarz, food])
    await session.flush()
    groceries = ExpenseCategory(family_budget_id=budget.id, name="Groceries", parent_id=food.id)
    session.add(groceries)
    await session.flush()
    for cat, amount in ((qarz, 700), (food, 50), (groceries, 100)):
        session.add(
            Transaction(
                family_budget_id=budget.id,
                type="expense",
                wallet_id=wallet.id,
                amount=amount,
                expense_category_id=cat.id,
                created_by_user_id=user.id,
                transaction_date=SELECTED_MONTH_DATE,
            )
        )
    await session.flush()
    return qarz, food, groceries


async def test_by_category_includes_expense_on_parent(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    tg = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    user, budget = await create_user_with_budget(session, telegram_id=tg)
    await _seed(session, budget, user)

    resp = await client.get(
        "/api/v1/analytics/expenses-by-category", headers=auth_headers(tg), params=PARAMS
    )
    assert resp.status_code == 200
    by_name = {r["category_name"]: r["amount"] for r in resp.json()}
    assert by_name == {"Qarz": 700, "Food": 150}
    assert sum(by_name.values()) == 850


async def test_by_subcategory_shows_parent_own_expense(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    tg = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    user, budget = await create_user_with_budget(session, telegram_id=tg)
    qarz, food, groceries = await _seed(session, budget, user)

    resp = await client.get(
        "/api/v1/analytics/expenses-by-subcategory",
        headers=auth_headers(tg),
        params={**PARAMS, "parent_category_id": str(food.id)},
    )
    assert resp.status_code == 200
    rows = {r["subcategory_id"]: r["amount"] for r in resp.json()}
    assert rows == {str(groceries.id): 100, str(food.id): 50}

    resp = await client.get(
        "/api/v1/analytics/expenses-by-subcategory",
        headers=auth_headers(tg),
        params={**PARAMS, "parent_category_id": str(qarz.id)},
    )
    assert resp.status_code == 200
    assert [(r["subcategory_id"], r["amount"]) for r in resp.json()] == [(str(qarz.id), 700)]


async def _seed_uncategorized(session: AsyncSession, budget, user):
    qarz, food, groceries = await _seed(session, budget, user)
    usd = Wallet(family_budget_id=budget.id, name="USD", currency="USD")
    personal = Wallet(
        family_budget_id=budget.id,
        name="Mine",
        currency="UZS",
        is_personal=True,
        owner_user_id=user.id,
    )
    wallet = (
        await session.execute(
            select(Wallet).where(Wallet.name == "W", Wallet.family_budget_id == budget.id)
        )
    ).scalar_one()
    session.add_all([usd, personal])
    await session.flush()
    for w, amount, deleted in ((wallet, 40, False), (wallet, 2, False), (usd, 9, False),
                               (personal, 5, False), (wallet, 3, True)):
        session.add(
            Transaction(
                family_budget_id=budget.id,
                type="expense",
                wallet_id=w.id,
                amount=amount,
                expense_category_id=None,
                created_by_user_id=user.id,
                transaction_date=SELECTED_MONTH_DATE,
                is_deleted=deleted,
            )
        )
    await session.flush()


async def test_by_category_has_uncategorized_row_summing_to_total(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    tg = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    user, budget = await create_user_with_budget(session, telegram_id=tg)
    await _seed_uncategorized(session, budget, user)

    resp = await client.get(
        "/api/v1/analytics/expenses-by-category", headers=auth_headers(tg), params=PARAMS
    )
    assert resp.status_code == 200
    rows = resp.json()
    unc = [r for r in rows if r["uncategorized"]]
    assert len(unc) == 1
    assert unc[0]["category_id"] is None
    assert unc[0]["amount"] == 42  # no USD, personal, deleted
    assert sum(r["amount"] for r in rows) == 892
    assert all(r["uncategorized"] is False for r in rows if r["category_id"])
    assert [r["amount"] for r in rows] == sorted((r["amount"] for r in rows), reverse=True)


async def test_by_category_no_uncategorized_row_when_none(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    tg = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    user, budget = await create_user_with_budget(session, telegram_id=tg)
    await _seed(session, budget, user)
    resp = await client.get(
        "/api/v1/analytics/expenses-by-category", headers=auth_headers(tg), params=PARAMS
    )
    assert not any(r["uncategorized"] for r in resp.json())


async def test_history_uncategorized_filter(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    tg = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    user, budget = await create_user_with_budget(session, telegram_id=tg)
    await _seed_uncategorized(session, budget, user)
    params = {
        "date_from": SELECTED_MONTH_START.isoformat(),
        "date_to": SELECTED_MONTH_END.isoformat(),
        "uncategorized": "true",
    }
    resp = await client.get("/api/v1/transactions/history", headers=auth_headers(tg), params=params)
    assert resp.status_code == 200
    body = resp.json()
    assert sorted(i["amount"] for i in body["items"] if i["currency"] == "UZS") == [2, 5, 40]  # incl. own personal wallet
    assert all(i["type"] == "expense" and i["expense_category_name"] is None for i in body["items"])
    assert body["total_count"] == len(body["items"])

    bad = await client.get(
        "/api/v1/transactions/history",
        headers=auth_headers(tg),
        params={**params, "expense_category_id": str(uuid.uuid4())},
    )
    assert bad.status_code == 422
