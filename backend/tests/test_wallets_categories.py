import json
import socket
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.telegram import sign_init_data
from app.db import engine, get_session
from app.main import app
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet

BOT_TOKEN = "5768337691:AAH5YkoiEuPk8-FZa32hStHTqXiLPtAEhx8"


def _db_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            return True
    except OSError:
        return False


async def _reset_engine() -> None:
    await engine.dispose()


@asynccontextmanager
async def rollback_session() -> AsyncIterator[AsyncSession]:
    await _reset_engine()
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await trans.rollback()
            await session.close()


def build_init_data(telegram_id: int) -> str:
    user_json = json.dumps(
        {"id": telegram_id, "first_name": "Test", "username": "testuser"},
        separators=(",", ":"),
    )
    fields = {
        "user": user_json,
        "auth_date": str(int(time.time())),
    }
    return sign_init_data(fields, BOT_TOKEN)


async def create_user_with_budget(
    session: AsyncSession,
    *,
    telegram_id: int,
    role: str = "owner",
) -> tuple[User, FamilyBudget]:
    budget = FamilyBudget(invite_token=f"test-{uuid.uuid4()}")
    session.add(budget)
    await session.flush()
    user = User(
        telegram_id=telegram_id,
        family_budget_id=budget.id,
        role=role,
        language="ru",
    )
    session.add(user)
    await session.flush()
    return user, budget


def auth_headers(telegram_id: int) -> dict[str, str]:
    return {"Authorization": f"tma {build_init_data(telegram_id)}"}


@pytest.fixture
async def api_client() -> AsyncIterator[tuple[AsyncClient, AsyncSession]]:
    await _reset_engine()
    conn = await engine.connect()
    trans = await conn.begin()
    session = AsyncSession(
        bind=conn,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_get_session

    with patch("app.main.verify_postgres_connection", new=AsyncMock()):
        with patch("app.auth.telegram.BOT_TOKEN", BOT_TOKEN):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                yield client, session

    await trans.rollback()
    await session.close()
    await conn.close()
    await _reset_engine()
    app.dependency_overrides.clear()


pytestmark = [
    pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available"),
    pytest.mark.anyio,
]


class TestMigrationCheckConstraint:
    async def test_wallets_currency_check_constraint_exists(self) -> None:
        await _reset_engine()
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'ck_wallets_currency'
                      AND conrelid = 'wallets'::regclass
                    """
                )
            )
            assert result.scalar_one_or_none() == 1


class TestTransactionQueryIndexes:
    async def test_partial_indexes_exist_with_expected_predicates(self) -> None:
        await _reset_engine()
        expected_names = {
            "ix_transactions_wallet_id_active",
            "ix_transactions_to_wallet_id_active",
            "ix_transactions_income_category_id_active",
            "ix_transactions_expense_category_id_active",
            "ix_transactions_family_date_id_active",
        }
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT
                        indexname,
                        indexdef
                    FROM pg_indexes
                    WHERE schemaname = current_schema()
                      AND tablename = 'transactions'
                    """
                )
            )
            indexes = {
                row.indexname: row.indexdef
                for row in result
                if row.indexname in expected_names
            }

        assert set(indexes) == expected_names
        assert all(
            "WHERE" in indexdef
            and ("NOT is_deleted" in indexdef or "is_deleted = false" in indexdef)
            for indexdef in indexes.values()
        )
        for nullable_column in (
            "to_wallet_id",
            "income_category_id",
            "expense_category_id",
        ):
            assert f"({nullable_column} IS NOT NULL)" in indexes[
                f"ix_transactions_{nullable_column}_active"
            ]
        assert "(family_budget_id, transaction_date DESC, id DESC)" in indexes[
            "ix_transactions_family_date_id_active"
        ]


class TestWalletsApi:
    async def test_owner_crud_and_get_excludes_deleted_with_transaction_count(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        active_wallet = Wallet(
            family_budget_id=budget.id,
            name="Active",
            currency="UZS",
        )
        deleted_wallet = Wallet(
            family_budget_id=budget.id,
            name="Deleted",
            currency="USD",
            is_deleted=True,
            deleted_at=datetime.now(UTC),
        )
        session.add_all([active_wallet, deleted_wallet])
        await session.flush()
        session.add(
            Transaction(
                family_budget_id=budget.id,
                type="income",
                wallet_id=active_wallet.id,
                amount=100,
                created_by_user_id=user.id,
                transaction_date=datetime.now(UTC),
            )
        )
        session.add(
            Transaction(
                family_budget_id=budget.id,
                type="transfer",
                wallet_id=deleted_wallet.id,
                to_wallet_id=active_wallet.id,
                amount=50,
                to_amount=50,
                created_by_user_id=user.id,
                transaction_date=datetime.now(UTC),
            )
        )
        await session.flush()
        headers = auth_headers(telegram_id)

        create_resp = await client.post(
            "/api/v1/wallets",
            headers=headers,
            json={"name": "Cash UZS", "currency": "UZS"},
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        assert created["name"] == "Cash UZS"
        assert created["currency"] == "UZS"
        assert created["transaction_count"] == 0

        list_resp = await client.get("/api/v1/wallets", headers=headers)
        assert list_resp.status_code == 200
        wallets = list_resp.json()
        assert len(wallets) == 2
        wallet_ids = {wallet["id"] for wallet in wallets}
        assert str(active_wallet.id) in wallet_ids
        active_listed = next(wallet for wallet in wallets if wallet["id"] == str(active_wallet.id))
        assert set(active_listed) == {"id", "name", "currency", "translation_key", "transaction_count"}
        assert active_listed["transaction_count"] == 2

        patch_resp = await client.patch(
            f"/api/v1/wallets/{created['id']}",
            headers=headers,
            json={"name": "Renamed"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["name"] == "Renamed"

        delete_resp = await client.delete(f"/api/v1/wallets/{created['id']}", headers=headers)
        assert delete_resp.status_code == 200
        assert delete_resp.json()["affected_transactions_count"] == 0

        after_delete = await client.get("/api/v1/wallets", headers=headers)
        assert len(after_delete.json()) == 1

    async def test_create_wallet_rejects_invalid_currency(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        await create_user_with_budget(session, telegram_id=telegram_id)

        response = await client.post(
            "/api/v1/wallets",
            headers=auth_headers(telegram_id),
            json={"name": "EUR wallet", "currency": "EUR"},
        )
        assert response.status_code == 422

    async def test_patch_wallet_rejects_currency_change(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        wallet = Wallet(family_budget_id=budget.id, name="Cash", currency="UZS")
        session.add(wallet)
        await session.flush()

        response = await client.patch(
            f"/api/v1/wallets/{wallet.id}",
            headers=auth_headers(telegram_id),
            json={"name": "Cash", "currency": "USD"},
        )
        assert response.status_code == 422

    async def test_member_gets_403_on_wallet_writes(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        _, budget = await create_user_with_budget(session, telegram_id=telegram_id, role="member")
        wallet = Wallet(family_budget_id=budget.id, name="Shared", currency="UZS")
        session.add(wallet)
        await session.flush()
        headers = auth_headers(telegram_id)

        assert (await client.get("/api/v1/wallets", headers=headers)).status_code == 200
        assert (
            await client.post(
                "/api/v1/wallets",
                headers=headers,
                json={"name": "New", "currency": "UZS"},
            )
        ).status_code == 403
        assert (
            await client.patch(
                f"/api/v1/wallets/{wallet.id}",
                headers=headers,
                json={"name": "Nope"},
            )
        ).status_code == 403
        assert (await client.delete(f"/api/v1/wallets/{wallet.id}", headers=headers)).status_code == 403

    async def test_cross_family_wallet_access_returns_404(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        other_tid = owner_tid + 1
        await create_user_with_budget(session, telegram_id=owner_tid, role="owner")
        _, other_budget = await create_user_with_budget(session, telegram_id=other_tid, role="owner")
        wallet = Wallet(family_budget_id=other_budget.id, name="Other", currency="USD")
        session.add(wallet)
        await session.flush()
        headers = auth_headers(owner_tid)

        assert (
            await client.patch(
                f"/api/v1/wallets/{wallet.id}",
                headers=headers,
                json={"name": "Hack"},
            )
        ).status_code == 404
        assert (await client.delete(f"/api/v1/wallets/{wallet.id}", headers=headers)).status_code == 404


class TestIncomeCategoriesApi:
    async def test_income_category_delete_returns_affected_count_and_hides_from_get(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        category = IncomeCategory(family_budget_id=budget.id, name="Salary")
        wallet = Wallet(family_budget_id=budget.id, name="Main", currency="UZS")
        session.add_all([category, wallet])
        await session.flush()
        session.add(
            Transaction(
                family_budget_id=budget.id,
                type="income",
                wallet_id=wallet.id,
                amount=500,
                income_category_id=category.id,
                created_by_user_id=user.id,
                transaction_date=datetime.now(UTC),
            )
        )
        await session.flush()
        headers = auth_headers(telegram_id)

        listed = (await client.get("/api/v1/categories/income", headers=headers)).json()
        assert listed[0]["transaction_count"] == 1

        deleted = await client.delete(f"/api/v1/categories/income/{category.id}", headers=headers)
        assert deleted.status_code == 200
        assert deleted.json()["affected_transactions_count"] == 1
        assert (await client.get("/api/v1/categories/income", headers=headers)).json() == []

        txn = await session.scalar(select(Transaction))
        assert txn is not None and txn.is_deleted is False


class TestExpenseCategoriesApi:
    async def test_expense_category_create_and_parent_validation(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        headers = auth_headers(telegram_id)

        top_resp = await client.post(
            "/api/v1/categories/expense",
            headers=headers,
            json={"name": "Тест"},
        )
        assert top_resp.status_code == 201
        top_id = top_resp.json()["id"]
        assert top_resp.json()["parent_id"] is None

        sub_resp = await client.post(
            "/api/v1/categories/expense",
            headers=headers,
            json={"name": "Подкатегория", "parent_id": top_id},
        )
        assert sub_resp.status_code == 201
        assert sub_resp.json()["parent_id"] == top_id

        nested_resp = await client.post(
            "/api/v1/categories/expense",
            headers=headers,
            json={"name": "Too deep", "parent_id": sub_resp.json()["id"]},
        )
        assert nested_resp.status_code == 400

        wallet = Wallet(family_budget_id=budget.id, name="Main", currency="UZS")
        session.add(wallet)
        await session.flush()
        session.add(
            Transaction(
                family_budget_id=budget.id,
                type="expense",
                wallet_id=wallet.id,
                amount=100,
                expense_category_id=uuid.UUID(sub_resp.json()["id"]),
                created_by_user_id=user.id,
                transaction_date=datetime.now(UTC),
            )
        )
        await session.flush()

        listed = (await client.get("/api/v1/categories/expense", headers=headers)).json()
        assert len(listed) == 2
        by_id = {category["id"]: category for category in listed}
        assert set(by_id[top_id]) == {"id", "name", "translation_key", "parent_id", "transaction_count"}
        assert by_id[top_id]["transaction_count"] == 0
        assert by_id[sub_resp.json()["id"]]["transaction_count"] == 1

    async def test_expense_top_level_delete_cascades_subcategories(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        top = ExpenseCategory(family_budget_id=budget.id, name="Parent")
        session.add(top)
        await session.flush()
        session.add_all(
            [
                ExpenseCategory(family_budget_id=budget.id, name="Sub 1", parent_id=top.id),
                ExpenseCategory(family_budget_id=budget.id, name="Sub 2", parent_id=top.id),
            ]
        )
        await session.flush()
        headers = auth_headers(telegram_id)

        delete_resp = await client.delete(f"/api/v1/categories/expense/{top.id}", headers=headers)
        assert delete_resp.status_code == 200

        rows = (
            await session.scalars(
                select(ExpenseCategory).where(ExpenseCategory.family_budget_id == budget.id)
            )
        ).all()
        assert len(rows) == 3 and all(row.is_deleted for row in rows)
        assert (await client.get("/api/v1/categories/expense", headers=headers)).json() == []


class TestMemberWriteForbiddenOnCategories:
    async def test_member_gets_403_on_category_writes(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        _, budget = await create_user_with_budget(session, telegram_id=telegram_id, role="member")
        income = IncomeCategory(family_budget_id=budget.id, name="Income")
        expense = ExpenseCategory(family_budget_id=budget.id, name="Expense")
        session.add_all([income, expense])
        await session.flush()
        headers = auth_headers(telegram_id)

        assert (await client.get("/api/v1/categories/income", headers=headers)).status_code == 200
        assert (await client.get("/api/v1/categories/expense", headers=headers)).status_code == 200

        write_cases = [
            ("post", "/api/v1/categories/income", {"name": "New income"}),
            ("patch", f"/api/v1/categories/income/{income.id}", {"name": "Nope"}),
            ("delete", f"/api/v1/categories/income/{income.id}", None),
            ("post", "/api/v1/categories/expense", {"name": "New expense"}),
            ("patch", f"/api/v1/categories/expense/{expense.id}", {"name": "Nope"}),
            ("delete", f"/api/v1/categories/expense/{expense.id}", None),
        ]
        for method, url, body in write_cases:
            response = await client.request(method, url, headers=headers, json=body)
            assert response.status_code == 403, f"{method.upper()} {url} expected 403"


class TestCrossFamilyCategoryAccess:
    async def test_cross_family_category_access_returns_404(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        other_tid = owner_tid + 1
        await create_user_with_budget(session, telegram_id=owner_tid, role="owner")
        _, other_budget = await create_user_with_budget(session, telegram_id=other_tid, role="owner")
        income = IncomeCategory(family_budget_id=other_budget.id, name="Other income")
        expense = ExpenseCategory(family_budget_id=other_budget.id, name="Other expense")
        session.add_all([income, expense])
        await session.flush()
        headers = auth_headers(owner_tid)

        assert (
            await client.patch(
                f"/api/v1/categories/income/{income.id}",
                headers=headers,
                json={"name": "Hack"},
            )
        ).status_code == 404
        assert (
            await client.delete(f"/api/v1/categories/income/{income.id}", headers=headers)
        ).status_code == 404
        assert (
            await client.patch(
                f"/api/v1/categories/expense/{expense.id}",
                headers=headers,
                json={"name": "Hack"},
            )
        ).status_code == 404
        assert (
            await client.delete(f"/api/v1/categories/expense/{expense.id}", headers=headers)
        ).status_code == 404


class TestListingQueryCounts:
    async def test_each_listing_uses_one_query_after_authentication(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        session.add_all(
            [
                Wallet(family_budget_id=budget.id, name="Wallet 1", currency="UZS"),
                Wallet(family_budget_id=budget.id, name="Wallet 2", currency="USD"),
                IncomeCategory(family_budget_id=budget.id, name="Income 1"),
                IncomeCategory(family_budget_id=budget.id, name="Income 2"),
                ExpenseCategory(family_budget_id=budget.id, name="Expense 1"),
                ExpenseCategory(family_budget_id=budget.id, name="Expense 2"),
            ]
        )
        await session.flush()

        select_statements: list[str] = []

        def record_select(
            _conn: object,
            _cursor: object,
            statement: str,
            _parameters: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            if statement.lstrip().upper().startswith("SELECT"):
                select_statements.append(statement)

        event.listen(engine.sync_engine, "before_cursor_execute", record_select)
        try:
            for path, expected_keys in (
                (
                    "/api/v1/wallets",
                    {"id", "name", "currency", "translation_key", "transaction_count"},
                ),
                (
                    "/api/v1/categories/income",
                    {"id", "name", "translation_key", "transaction_count"},
                ),
                (
                    "/api/v1/categories/expense",
                    {"id", "name", "translation_key", "parent_id", "transaction_count"},
                ),
            ):
                select_statements.clear()
                response = await client.get(path, headers=auth_headers(telegram_id))
                assert response.status_code == 200
                assert len(select_statements) == 2
                assert all(set(item) == expected_keys for item in response.json())
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", record_select)
