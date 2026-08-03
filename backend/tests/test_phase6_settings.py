import socket
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.wallet import Wallet
from app.services.entity_limits import (
    LIMIT_EXPENSE_PARENTS,
    LIMIT_INCOME_CATEGORIES,
    LIMIT_SHARED_WALLETS,
    limit_subcategories,
)
from tests.test_wallets_categories import (
    api_client,
    auth_headers,
    create_user_with_budget,
)


def _db_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available"),
    pytest.mark.anyio,
]


async def test_shared_wallet_11th_returns_exact_19_1(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
    headers = auth_headers(telegram_id)

    for i in range(10):
        session.add(
            Wallet(
                family_budget_id=budget.id,
                name=f"Shared {i}",
                currency="UZS",
                is_personal=False,
            )
        )
    await session.flush()

    response = await client.post(
        "/api/v1/wallets",
        headers=headers,
        json={"name": "Eleventh", "currency": "UZS"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == LIMIT_SHARED_WALLETS


async def test_delete_shared_frees_slot(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
    headers = auth_headers(telegram_id)

    wallets = [
        Wallet(
            family_budget_id=budget.id,
            name=f"Shared {i}",
            currency="UZS",
            is_personal=False,
        )
        for i in range(10)
    ]
    session.add_all(wallets)
    await session.flush()

    delete_resp = await client.delete(
        f"/api/v1/wallets/{wallets[0].id}",
        headers=headers,
    )
    assert delete_resp.status_code == 200

    create_resp = await client.post(
        "/api/v1/wallets",
        headers=headers,
        json={"name": "Replacement", "currency": "UZS"},
    )
    assert create_resp.status_code == 201


async def test_wallet_name_31_rejected(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    await create_user_with_budget(session, telegram_id=telegram_id)

    response = await client.post(
        "/api/v1/wallets",
        headers=auth_headers(telegram_id),
        json={"name": "a" * 31, "currency": "UZS"},
    )
    assert response.status_code == 422


async def test_wallet_name_only_spaces_rejected(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    await create_user_with_budget(session, telegram_id=telegram_id)

    response = await client.post(
        "/api/v1/wallets",
        headers=auth_headers(telegram_id),
        json={"name": "   ", "currency": "UZS"},
    )
    assert response.status_code == 422


async def test_expense_parent_9th_exact_message(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
    headers = auth_headers(telegram_id)

    for i in range(8):
        session.add(ExpenseCategory(family_budget_id=budget.id, name=f"Parent {i}"))
    await session.flush()

    response = await client.post(
        "/api/v1/categories/expense",
        headers=headers,
        json={"name": "Ninth parent"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == LIMIT_EXPENSE_PARENTS


async def test_subcategory_9th_under_food_exact_message(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
    headers = auth_headers(telegram_id)

    parent = ExpenseCategory(family_budget_id=budget.id, name="Еда")
    session.add(parent)
    await session.flush()
    session.add_all(
        [
            ExpenseCategory(
                family_budget_id=budget.id,
                name=f"Sub {i}",
                parent_id=parent.id,
            )
            for i in range(8)
        ]
    )
    await session.flush()

    response = await client.post(
        "/api/v1/categories/expense",
        headers=headers,
        json={"name": "Ninth sub", "parent_id": str(parent.id)},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == limit_subcategories("Еда")


async def test_income_9th_exact_message(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
    headers = auth_headers(telegram_id)

    for i in range(8):
        session.add(IncomeCategory(family_budget_id=budget.id, name=f"Income {i}"))
    await session.flush()

    response = await client.post(
        "/api/v1/categories/income",
        headers=headers,
        json={"name": "Ninth income"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == LIMIT_INCOME_CATEGORIES


async def test_deleted_category_frees_parent_slot(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
    headers = auth_headers(telegram_id)

    categories = [
        ExpenseCategory(family_budget_id=budget.id, name=f"Parent {i}")
        for i in range(8)
    ]
    session.add_all(categories)
    await session.flush()

    delete_resp = await client.delete(
        f"/api/v1/categories/expense/{categories[0].id}",
        headers=headers,
    )
    assert delete_resp.status_code == 200

    create_resp = await client.post(
        "/api/v1/categories/expense",
        headers=headers,
        json={"name": "Replacement parent"},
    )
    assert create_resp.status_code == 201


async def test_new_income_category_gets_smallest_free_color(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
    headers = auth_headers(telegram_id)

    for color_index in (1, 2, 3):
        session.add(
            IncomeCategory(
                family_budget_id=budget.id,
                name=f"Income {color_index}",
                color_index=color_index,
            )
        )
    await session.flush()

    response = await client.post(
        "/api/v1/categories/income",
        headers=headers,
        json={"name": "Fourth income"},
    )
    assert response.status_code == 201
    assert response.json()["color_index"] == 4


async def test_delete_parent_reuses_longest_deleted_color(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
    headers = auth_headers(telegram_id)

    for color_index in range(1, 9):
        session.add(
            ExpenseCategory(
                family_budget_id=budget.id,
                name=f"Active {color_index}",
                color_index=color_index,
            )
        )
    await session.flush()

    to_delete = await session.scalar(
        select(ExpenseCategory).where(
            ExpenseCategory.family_budget_id == budget.id,
            ExpenseCategory.color_index == 5,
            ExpenseCategory.is_deleted.is_(False),
        )
    )
    assert to_delete is not None

    delete_resp = await client.delete(
        f"/api/v1/categories/expense/{to_delete.id}",
        headers=headers,
    )
    assert delete_resp.status_code == 200

    create_resp = await client.post(
        "/api/v1/categories/expense",
        headers=headers,
        json={"name": "Replacement"},
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["color_index"] == 5


async def test_no_free_color_reuses_oldest_deleted_color(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
    headers = auth_headers(telegram_id)

    now = datetime.now(UTC)
    for color_index in range(1, 9):
        session.add(
            ExpenseCategory(
                family_budget_id=budget.id,
                name=f"Deleted {color_index}",
                color_index=color_index,
                is_deleted=True,
                deleted_at=now - timedelta(days=300 - color_index),
            )
        )
    for color_index in range(1, 9):
        session.add(
            ExpenseCategory(
                family_budget_id=budget.id,
                name=f"Active {color_index}",
                color_index=color_index,
            )
        )
    await session.flush()

    to_delete = await session.scalar(
        select(ExpenseCategory).where(
            ExpenseCategory.family_budget_id == budget.id,
            ExpenseCategory.name == "Active 1",
        )
    )
    assert to_delete is not None

    delete_resp = await client.delete(
        f"/api/v1/categories/expense/{to_delete.id}",
        headers=headers,
    )
    assert delete_resp.status_code == 200

    create_resp = await client.post(
        "/api/v1/categories/expense",
        headers=headers,
        json={"name": "Ninth attempt"},
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["color_index"] == 1


async def test_soft_deleted_category_keeps_color_in_analytics(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
    headers = auth_headers(telegram_id)

    wallet = Wallet(family_budget_id=budget.id, name="Cash", currency="UZS")
    income_cat = IncomeCategory(
        family_budget_id=budget.id,
        name="Зарплата",
        translation_key="salary",
        color_index=5,
        is_deleted=True,
        deleted_at=datetime.now(UTC),
    )
    session.add_all([wallet, income_cat])
    await session.flush()

    dt = datetime(2026, 11, 1, tzinfo=UTC)
    session.add(
        Transaction(
            family_budget_id=budget.id,
            type="income",
            wallet_id=wallet.id,
            amount=1000,
            income_category_id=income_cat.id,
            created_by_user_id=user.id,
            transaction_date=dt,
        )
    )
    await session.flush()

    response = await client.get(
        "/api/v1/analytics/income-by-category",
        headers=headers,
        params={
            "currency": "UZS",
            "date_from": dt.isoformat(),
            "date_to": datetime(2026, 11, 30, tzinfo=UTC).isoformat(),
        },
    )
    assert response.status_code == 200
    row = response.json()[0]
    assert row["category_name"] == "Зарплата"
    assert row["color_index"] == 5
