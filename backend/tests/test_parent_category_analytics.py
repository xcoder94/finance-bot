"""Expenses booked directly on a parent category must appear in category analytics."""

import uuid

from httpx import AsyncClient
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
