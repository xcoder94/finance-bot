import socket
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.services.budget_seed import copy_seed_categories_only, copy_seed_data
from app.services.entity_limits import LIMIT_EXPENSE_PARENTS
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


async def _reset_engine() -> None:
    await engine.dispose()


pytestmark = [
    pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available"),
    pytest.mark.anyio,
]


@pytest.mark.anyio
async def test_is_protected_column_exists_not_null_default_false():
    await _reset_engine()
    async with engine.connect() as conn:
        def check(sync_conn):
            cols = {c["name"]: c for c in inspect(sync_conn).get_columns("expense_categories")}
            assert "is_protected" in cols
            assert cols["is_protected"]["nullable"] is False

        await conn.run_sync(check)


@pytest.mark.anyio
async def test_new_expense_category_defaults_is_protected_false(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    _, session = api_client
    budget = FamilyBudget(invite_token=f"test-{uuid.uuid4()}")
    session.add(budget)
    await session.flush()

    cat = ExpenseCategory(
        family_budget_id=budget.id,
        name="Тест",
        parent_id=None,
        color_index=1,
    )
    session.add(cat)
    await session.flush()
    await session.refresh(cat)
    assert cat.is_protected is False


async def _get_parent_by_key(
    session: AsyncSession, budget_id: uuid.UUID, key: str
) -> ExpenseCategory:
    parent = await session.scalar(
        select(ExpenseCategory).where(
            ExpenseCategory.family_budget_id == budget_id,
            ExpenseCategory.translation_key == key,
            ExpenseCategory.parent_id.is_(None),
        )
    )
    assert parent is not None
    return parent


async def test_seed_sets_protection_on_food_home_health_only(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    _, session = api_client
    budget = FamilyBudget(invite_token=f"seed-{uuid.uuid4()}")
    session.add(budget)
    await session.flush()
    await copy_seed_categories_only(session, budget.id)

    for key in ("food", "home", "health"):
        parent = await _get_parent_by_key(session, budget.id, key)
        assert parent.is_protected is True

    transport = await _get_parent_by_key(session, budget.id, "transport")
    assert transport.is_protected is False

    subs = (
        await session.scalars(
            select(ExpenseCategory).where(
                ExpenseCategory.family_budget_id == budget.id,
                ExpenseCategory.parent_id.is_not(None),
            )
        )
    ).all()
    assert subs
    assert all(sub.is_protected is False for sub in subs)


async def test_delete_protected_parent_returns_403(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
    headers = auth_headers(telegram_id)
    await copy_seed_data(session, budget.id)

    food = await _get_parent_by_key(session, budget.id, "food")
    response = await client.delete(
        f"/api/v1/categories/expense/{food.id}",
        headers=headers,
    )
    assert response.status_code == 403


async def test_patch_protected_parent_returns_403(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
    headers = auth_headers(telegram_id)
    await copy_seed_data(session, budget.id)

    home = await _get_parent_by_key(session, budget.id, "home")
    response = await client.patch(
        f"/api/v1/categories/expense/{home.id}",
        headers=headers,
        json={"name": "Новый дом"},
    )
    assert response.status_code == 403


async def test_delete_unprotected_parent_succeeds(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
    headers = auth_headers(telegram_id)
    await copy_seed_data(session, budget.id)

    transport = await _get_parent_by_key(session, budget.id, "transport")
    response = await client.delete(
        f"/api/v1/categories/expense/{transport.id}",
        headers=headers,
    )
    assert response.status_code == 200


async def test_patch_subcategory_under_protected_parent_succeeds(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
    headers = auth_headers(telegram_id)
    await copy_seed_data(session, budget.id)

    food = await _get_parent_by_key(session, budget.id, "food")
    sub = await session.scalar(
        select(ExpenseCategory).where(
            ExpenseCategory.family_budget_id == budget.id,
            ExpenseCategory.parent_id == food.id,
            ExpenseCategory.translation_key == "groceries",
        )
    )
    assert sub is not None

    response = await client.patch(
        f"/api/v1/categories/expense/{sub.id}",
        headers=headers,
        json={"name": "Продукты обновлённые"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Продукты обновлённые"


async def test_delete_subcategory_under_protected_parent_succeeds(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
    headers = auth_headers(telegram_id)
    await copy_seed_data(session, budget.id)

    food = await _get_parent_by_key(session, budget.id, "food")
    sub = await session.scalar(
        select(ExpenseCategory).where(
            ExpenseCategory.family_budget_id == budget.id,
            ExpenseCategory.parent_id == food.id,
            ExpenseCategory.translation_key == "delivery",
        )
    )
    assert sub is not None

    response = await client.delete(
        f"/api/v1/categories/expense/{sub.id}",
        headers=headers,
    )
    assert response.status_code == 200


async def test_limit_counts_only_non_protected_parents(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
    headers = auth_headers(telegram_id)
    await copy_seed_data(session, budget.id)

    # Seeded: 3 protected + 4 unprotected parents. Add 4 more unprotected → 8 total.
    for i in range(4):
        response = await client.post(
            "/api/v1/categories/expense",
            headers=headers,
            json={"name": f"Custom {i}"},
        )
        assert response.status_code == 201

    ninth = await client.post(
        "/api/v1/categories/expense",
        headers=headers,
        json={"name": "Ninth non-protected"},
    )
    assert ninth.status_code == 409
    assert ninth.json()["detail"] == LIMIT_EXPENSE_PARENTS


async def test_legacy_food_parent_without_protection_still_editable(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
    headers = auth_headers(telegram_id)

    legacy_food = ExpenseCategory(
        family_budget_id=budget.id,
        name="Еда",
        parent_id=None,
        translation_key="food",
        color_index=1,
        is_protected=False,
    )
    session.add(legacy_food)
    await session.flush()

    patch_resp = await client.patch(
        f"/api/v1/categories/expense/{legacy_food.id}",
        headers=headers,
        json={"name": "Еда переименована"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Еда переименована"

    delete_resp = await client.delete(
        f"/api/v1/categories/expense/{legacy_food.id}",
        headers=headers,
    )
    assert delete_resp.status_code == 200
