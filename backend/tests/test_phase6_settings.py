import socket
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from app.models.income_category import IncomeCategory
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
