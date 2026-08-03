import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from tests.test_history_analytics import (
    api_client,
    auth_headers,
    create_user_with_budget,
    pytestmark,
)

SELECTED_MONTH_START = datetime(2026, 3, 1, tzinfo=UTC)
SELECTED_MONTH_END = datetime(2026, 3, 31, 23, 59, 59, tzinfo=UTC)
PREVIOUS_MONTH_DATE = datetime(2026, 2, 15, tzinfo=UTC)
SELECTED_MONTH_DATE = datetime(2026, 3, 10, tzinfo=UTC)

SHARED_FOOD_UZS = 1_000
PERSONAL_FOOD_UZS = 500
SHARED_TRANSPORT_UZS = 300
SHARED_FOOD_PREV_MONTH = 200
SHARED_FOOD_USD = 40


async def seed_phase5_fixtures(
    session: AsyncSession,
    budget: FamilyBudget,
    user: User,
) -> dict[str, object]:
    wallet_uzs = Wallet(family_budget_id=budget.id, name="Shared UZS", currency="UZS")
    wallet_usd = Wallet(family_budget_id=budget.id, name="Shared USD", currency="USD")
    wallet_personal = Wallet(
        family_budget_id=budget.id,
        name="Personal UZS",
        currency="UZS",
        is_personal=True,
        owner_user_id=user.id,
    )
    income_cat = IncomeCategory(family_budget_id=budget.id, name="Salary")
    food = ExpenseCategory(family_budget_id=budget.id, name="Food")
    transport = ExpenseCategory(family_budget_id=budget.id, name="Transport")
    session.add_all(
        [wallet_uzs, wallet_usd, wallet_personal, income_cat, food, transport]
    )
    await session.flush()

    food_groceries = ExpenseCategory(
        family_budget_id=budget.id, name="Groceries", parent_id=food.id
    )
    food_restaurants = ExpenseCategory(
        family_budget_id=budget.id, name="Restaurants", parent_id=food.id
    )
    transport_taxi = ExpenseCategory(
        family_budget_id=budget.id, name="Taxi", parent_id=transport.id
    )
    session.add_all([food_groceries, food_restaurants, transport_taxi])
    await session.flush()

    session.add_all(
        [
            Transaction(
                family_budget_id=budget.id,
                type="expense",
                wallet_id=wallet_uzs.id,
                amount=SHARED_FOOD_UZS,
                expense_category_id=food_groceries.id,
                created_by_user_id=user.id,
                transaction_date=SELECTED_MONTH_DATE,
            ),
            Transaction(
                family_budget_id=budget.id,
                type="expense",
                wallet_id=wallet_personal.id,
                amount=PERSONAL_FOOD_UZS,
                expense_category_id=food_restaurants.id,
                created_by_user_id=user.id,
                transaction_date=SELECTED_MONTH_DATE,
            ),
            Transaction(
                family_budget_id=budget.id,
                type="expense",
                wallet_id=wallet_uzs.id,
                amount=SHARED_TRANSPORT_UZS,
                expense_category_id=transport_taxi.id,
                created_by_user_id=user.id,
                transaction_date=SELECTED_MONTH_DATE,
            ),
            Transaction(
                family_budget_id=budget.id,
                type="expense",
                wallet_id=wallet_uzs.id,
                amount=SHARED_FOOD_PREV_MONTH,
                expense_category_id=food_groceries.id,
                created_by_user_id=user.id,
                transaction_date=PREVIOUS_MONTH_DATE,
            ),
            Transaction(
                family_budget_id=budget.id,
                type="expense",
                wallet_id=wallet_usd.id,
                amount=SHARED_FOOD_USD,
                expense_category_id=food_groceries.id,
                created_by_user_id=user.id,
                transaction_date=SELECTED_MONTH_DATE,
            ),
        ]
    )
    await session.flush()

    return {
        "wallet_uzs": wallet_uzs,
        "wallet_usd": wallet_usd,
        "wallet_personal": wallet_personal,
        "food": food,
        "transport": transport,
        "food_groceries": food_groceries,
        "food_restaurants": food_restaurants,
        "transport_taxi": transport_taxi,
    }


class TestPersonalWalletExclusion:
    async def test_expenses_by_category_excludes_personal_wallet(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        await seed_phase5_fixtures(session, budget, user)

        resp = await client.get(
            "/api/v1/analytics/expenses-by-category",
            headers=auth_headers(telegram_id),
            params={
                "currency": "UZS",
                "date_from": SELECTED_MONTH_START.isoformat(),
                "date_to": SELECTED_MONTH_END.isoformat(),
            },
        )
        assert resp.status_code == 200
        by_name = {row["category_name"]: row["amount"] for row in resp.json()}
        assert by_name["Food"] == SHARED_FOOD_UZS
        assert by_name["Transport"] == SHARED_TRANSPORT_UZS
        assert sum(by_name.values()) == SHARED_FOOD_UZS + SHARED_TRANSPORT_UZS
        assert PERSONAL_FOOD_UZS not in by_name.values()

    async def test_summary_excludes_personal_wallet_expense(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        await seed_phase5_fixtures(session, budget, user)

        resp = await client.get(
            "/api/v1/analytics/summary",
            headers=auth_headers(telegram_id),
            params={
                "date_from": SELECTED_MONTH_START.isoformat(),
                "date_to": SELECTED_MONTH_END.isoformat(),
            },
        )
        assert resp.status_code == 200
        by_currency = {row["currency"]: row for row in resp.json()["by_currency"]}
        assert by_currency["UZS"]["expense"] == SHARED_FOOD_UZS + SHARED_TRANSPORT_UZS
        assert by_currency["USD"]["expense"] == SHARED_FOOD_USD

    async def test_trend_excludes_personal_wallet_expense(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        await seed_phase5_fixtures(session, budget, user)

        now = datetime(2026, 3, 20, tzinfo=UTC)
        with patch("app.services.history_analytics.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            resp = await client.get(
                "/api/v1/analytics/trend",
                headers=auth_headers(telegram_id),
            )

        assert resp.status_code == 200
        march_uzs = next(
            e for e in resp.json() if e["month"] == "2026-03" and e["currency"] == "UZS"
        )
        feb_uzs = next(
            e for e in resp.json() if e["month"] == "2026-02" and e["currency"] == "UZS"
        )
        assert march_uzs["expense"] == SHARED_FOOD_UZS + SHARED_TRANSPORT_UZS
        assert feb_uzs["expense"] == SHARED_FOOD_PREV_MONTH

    async def test_history_still_includes_personal_wallet_ops(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        await seed_phase5_fixtures(session, budget, user)

        resp = await client.get(
            "/api/v1/transactions/history",
            headers=auth_headers(telegram_id),
            params={
                "date_from": SELECTED_MONTH_START.isoformat(),
                "date_to": SELECTED_MONTH_END.isoformat(),
            },
        )
        assert resp.status_code == 200
        amounts = {item["amount"] for item in resp.json()["items"]}
        assert PERSONAL_FOOD_UZS in amounts
