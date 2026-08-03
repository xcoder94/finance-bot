import socket
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine, get_session
from app.main import app
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.history_analytics import (
    default_calendar_year_range,
    get_summary,
    get_trend,
    should_include_created_by,
)
from tests.auth_helpers import TEST_APP_PASS_SECRET, bearer_header_for_telegram_id


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


async def create_user_with_budget(
    session: AsyncSession,
    *,
    telegram_id: int,
    role: str = "owner",
    first_name: str | None = None,
) -> tuple[User, FamilyBudget]:
    budget = FamilyBudget(invite_token=f"test-{uuid.uuid4()}")
    session.add(budget)
    await session.flush()
    user = User(
        telegram_id=telegram_id,
        family_budget_id=budget.id,
        role=role,
        language="ru",
        first_name=first_name,
    )
    session.add(user)
    await session.flush()
    return user, budget


def auth_headers(telegram_id: int) -> dict[str, str]:
    return bearer_header_for_telegram_id(telegram_id)


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
        with patch("app.auth.deps.APP_PASS_SECRET", TEST_APP_PASS_SECRET):
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


async def seed_fixtures(
    session: AsyncSession,
    budget: FamilyBudget,
    user: User,
) -> dict[str, object]:
    wallet_uzs = Wallet(family_budget_id=budget.id, name="Cash UZS", currency="UZS")
    wallet_usd = Wallet(family_budget_id=budget.id, name="Cash USD", currency="USD")
    income_cat = IncomeCategory(family_budget_id=budget.id, name="Salary")
    expense_top = ExpenseCategory(family_budget_id=budget.id, name="Food")
    session.add_all([wallet_uzs, wallet_usd, income_cat, expense_top])
    await session.flush()
    expense_sub_a = ExpenseCategory(
        family_budget_id=budget.id, name="Groceries", parent_id=expense_top.id
    )
    expense_sub_b = ExpenseCategory(
        family_budget_id=budget.id, name="Restaurants", parent_id=expense_top.id
    )
    session.add_all([expense_sub_a, expense_sub_b])
    await session.flush()
    return {
        "wallet_uzs": wallet_uzs,
        "wallet_usd": wallet_usd,
        "income_cat": income_cat,
        "expense_top": expense_top,
        "expense_sub_a": expense_sub_a,
        "expense_sub_b": expense_sub_b,
        "user": user,
    }


class TestHistoryEndpoint:
    async def test_pagination_and_sorting(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        fx = await seed_fixtures(session, budget, user)

        dates = [
            datetime(2026, 3, 10, 12, 0, tzinfo=UTC),
            datetime(2026, 3, 11, 12, 0, tzinfo=UTC),
            datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
        ]
        for idx, dt in enumerate(dates):
            session.add(
                Transaction(
                    family_budget_id=budget.id,
                    type="income",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=100 * (idx + 1),
                    income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=dt,
                )
            )
        await session.flush()

        headers = auth_headers(telegram_id)
        date_from = datetime(2026, 3, 1, tzinfo=UTC).isoformat()
        date_to = datetime(2026, 3, 31, 23, 59, 59, tzinfo=UTC).isoformat()

        page1 = await client.get(
            "/api/v1/transactions/history",
            headers=headers,
            params={"date_from": date_from, "date_to": date_to, "limit": 2, "offset": 0},
        )
        assert page1.status_code == 200, page1.text
        body1 = page1.json()
        assert body1["total_count"] == 3
        assert len(body1["items"]) == 2
        assert body1["items"][0]["amount"] == 300
        assert body1["items"][1]["amount"] == 200

        page2 = await client.get(
            "/api/v1/transactions/history",
            headers=headers,
            params={"date_from": date_from, "date_to": date_to, "limit": 2, "offset": 2},
        )
        assert page2.status_code == 200
        body2 = page2.json()
        assert len(body2["items"]) == 1
        assert body2["items"][0]["amount"] == 100

    async def test_date_validation_returns_422(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        await create_user_with_budget(session, telegram_id=telegram_id)
        headers = auth_headers(telegram_id)

        missing = await client.get("/api/v1/transactions/history", headers=headers)
        assert missing.status_code == 422

        inverted = await client.get(
            "/api/v1/transactions/history",
            headers=headers,
            params={
                "date_from": datetime(2026, 6, 1, tzinfo=UTC).isoformat(),
                "date_to": datetime(2026, 5, 1, tzinfo=UTC).isoformat(),
            },
        )
        assert inverted.status_code == 422

    async def test_excludes_soft_deleted_transactions(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        fx = await seed_fixtures(session, budget, user)
        dt = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)

        active = Transaction(
            family_budget_id=budget.id,
            type="income",
            wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
            amount=100,
            income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
            created_by_user_id=user.id,
            transaction_date=dt,
        )
        deleted = Transaction(
            family_budget_id=budget.id,
            type="income",
            wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
            amount=999,
            income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
            created_by_user_id=user.id,
            transaction_date=dt,
            is_deleted=True,
            deleted_at=datetime.now(UTC),
        )
        session.add_all([active, deleted])
        await session.flush()

        resp = await client.get(
            "/api/v1/transactions/history",
            headers=auth_headers(telegram_id),
            params={
                "date_from": datetime(2026, 4, 1, tzinfo=UTC).isoformat(),
                "date_to": datetime(2026, 4, 30, tzinfo=UTC).isoformat(),
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_count"] == 1
        assert body["items"][0]["amount"] == 100

    async def test_created_by_omitted_for_single_user_family(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id, first_name="Solo")
        fx = await seed_fixtures(session, budget, user)
        session.add(
            Transaction(
                family_budget_id=budget.id,
                type="income",
                wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                amount=100,
                income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                created_by_user_id=user.id,
                transaction_date=datetime(2026, 5, 1, tzinfo=UTC),
            )
        )
        await session.flush()

        resp = await client.get(
            "/api/v1/transactions/history",
            headers=auth_headers(telegram_id),
            params={
                "date_from": datetime(2026, 5, 1, tzinfo=UTC).isoformat(),
                "date_to": datetime(2026, 5, 31, tzinfo=UTC).isoformat(),
            },
        )
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert "created_by" not in item or item.get("created_by") is None

    async def test_single_user_history_counts_once_and_skips_user_join(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        fx = await seed_fixtures(session, budget, user)
        session.add(
            Transaction(
                family_budget_id=budget.id,
                type="income",
                wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                amount=100,
                income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                created_by_user_id=user.id,
                transaction_date=datetime(2026, 5, 1, tzinfo=UTC),
            )
        )
        await session.flush()

        statements: list[str] = []

        def record_select(
            _conn: object,
            _cursor: object,
            statement: str,
            _parameters: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement.lower())

        event.listen(engine.sync_engine, "before_cursor_execute", record_select)
        try:
            with patch(
                "app.api.v1.history.should_include_created_by",
                wraps=should_include_created_by,
            ) as include_mock:
                resp = await client.get(
                    "/api/v1/transactions/history",
                    headers=auth_headers(telegram_id),
                    params={
                        "date_from": datetime(2026, 5, 1, tzinfo=UTC).isoformat(),
                        "date_to": datetime(2026, 5, 31, tzinfo=UTC).isoformat(),
                    },
                )
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", record_select)

        assert resp.status_code == 200
        assert include_mock.await_count == 1
        history_statements = [
            statement
            for statement in statements
            if "from transactions" in statement and "join wallets" in statement
        ]
        assert len(history_statements) == 1
        assert "join users" not in history_statements[0]
        assert "users.first_name" not in history_statements[0]

    async def test_created_by_included_for_multi_user_family(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        member_tid = owner_tid + 1
        owner, budget = await create_user_with_budget(
            session, telegram_id=owner_tid, first_name="OwnerName"
        )
        member = User(
            telegram_id=member_tid,
            family_budget_id=budget.id,
            role="member",
            language="ru",
            first_name="MemberName",
        )
        session.add(member)
        await session.flush()
        fx = await seed_fixtures(session, budget, owner)

        for creator, amount in ((owner, 100), (member, 200)):
            session.add(
                Transaction(
                    family_budget_id=budget.id,
                    type="income",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=amount,
                    income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                    created_by_user_id=creator.id,
                    transaction_date=datetime(2026, 6, 1, tzinfo=UTC),
                )
            )
        await session.flush()

        resp = await client.get(
            "/api/v1/transactions/history",
            headers=auth_headers(owner_tid),
            params={
                "date_from": datetime(2026, 6, 1, tzinfo=UTC).isoformat(),
                "date_to": datetime(2026, 6, 30, tzinfo=UTC).isoformat(),
            },
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 2
        assert all(item["created_by"] is not None for item in items)
        names = {item["created_by"] for item in items}
        assert names == {"OwnerName", "MemberName"}

    async def test_created_by_included_when_only_soft_deleted_second_user(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        owner, budget = await create_user_with_budget(
            session, telegram_id=owner_tid, first_name="ActiveOwner"
        )
        removed = User(
            telegram_id=owner_tid + 99,
            family_budget_id=budget.id,
            role="member",
            language="ru",
            first_name="RemovedMember",
            is_deleted=True,
            deleted_at=datetime.now(UTC),
        )
        session.add(removed)
        await session.flush()
        fx = await seed_fixtures(session, budget, owner)
        session.add(
            Transaction(
                family_budget_id=budget.id,
                type="income",
                wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                amount=100,
                income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                created_by_user_id=owner.id,
                transaction_date=datetime(2026, 7, 1, tzinfo=UTC),
            )
        )
        await session.flush()

        resp = await client.get(
            "/api/v1/transactions/history",
            headers=auth_headers(owner_tid),
            params={
                "date_from": datetime(2026, 7, 1, tzinfo=UTC).isoformat(),
                "date_to": datetime(2026, 7, 31, tzinfo=UTC).isoformat(),
            },
        )
        assert resp.status_code == 200
        assert resp.json()["items"][0]["created_by"] == "ActiveOwner"

    async def test_soft_deleted_family_returns_403(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        _user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        budget.is_deleted = True
        budget.deleted_at = datetime.now(UTC)
        await session.flush()

        resp = await client.get(
            "/api/v1/transactions/history",
            headers=auth_headers(telegram_id),
            params={
                "date_from": datetime(2026, 5, 1, tzinfo=UTC).isoformat(),
                "date_to": datetime(2026, 5, 31, tzinfo=UTC).isoformat(),
            },
        )

        assert resp.status_code == 403


class TestTranslationKeysOnResponses:
    async def test_history_includes_translation_keys_for_soft_deleted_entities(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)

        wallet = Wallet(
            family_budget_id=budget.id,
            name="Карта сум",
            currency="UZS",
            translation_key="card_uzs",
            is_deleted=True,
            deleted_at=datetime.now(UTC),
        )
        income_cat = IncomeCategory(
            family_budget_id=budget.id,
            name="Зарплата",
            translation_key="salary",
            is_deleted=True,
            deleted_at=datetime.now(UTC),
        )
        expense_top = ExpenseCategory(
            family_budget_id=budget.id,
            name="Еда",
            translation_key="food",
            is_deleted=True,
            deleted_at=datetime.now(UTC),
        )
        session.add_all([wallet, income_cat, expense_top])
        await session.flush()
        expense_sub = ExpenseCategory(
            family_budget_id=budget.id,
            name="Продукты",
            parent_id=expense_top.id,
            translation_key="groceries",
            is_deleted=True,
            deleted_at=datetime.now(UTC),
        )
        session.add(expense_sub)
        await session.flush()

        dt = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
        session.add_all(
            [
                Transaction(
                    family_budget_id=budget.id,
                    type="income",
                    wallet_id=wallet.id,
                    amount=1000,
                    income_category_id=income_cat.id,
                    created_by_user_id=user.id,
                    transaction_date=dt,
                ),
                Transaction(
                    family_budget_id=budget.id,
                    type="expense",
                    wallet_id=wallet.id,
                    amount=500,
                    expense_category_id=expense_sub.id,
                    created_by_user_id=user.id,
                    transaction_date=dt,
                ),
            ]
        )
        await session.flush()

        resp = await client.get(
            "/api/v1/transactions/history",
            headers=auth_headers(telegram_id),
            params={
                "date_from": datetime(2026, 10, 1, tzinfo=UTC).isoformat(),
                "date_to": datetime(2026, 10, 31, tzinfo=UTC).isoformat(),
            },
        )
        assert resp.status_code == 200
        items = {item["type"]: item for item in resp.json()["items"]}

        income_item = items["income"]
        assert income_item["wallet_translation_key"] == "card_uzs"
        assert income_item["income_category_translation_key"] == "salary"
        assert income_item["wallet_name"] == "Карта сум"
        assert income_item["income_category_name"] == "Зарплата"

        expense_item = items["expense"]
        assert expense_item["wallet_translation_key"] == "card_uzs"
        assert expense_item["expense_category_translation_key"] == "food"
        assert expense_item["expense_subcategory_translation_key"] == "groceries"
        assert expense_item["expense_category_name"] == "Еда"
        assert expense_item["expense_subcategory_name"] == "Продукты"

    async def test_history_translation_keys_null_for_user_created_entities(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)

        wallet = Wallet(family_budget_id=budget.id, name="My Wallet", currency="UZS")
        income_cat = IncomeCategory(family_budget_id=budget.id, name="Custom Income")
        session.add_all([wallet, income_cat])
        await session.flush()

        session.add(
            Transaction(
                family_budget_id=budget.id,
                type="income",
                wallet_id=wallet.id,
                amount=100,
                income_category_id=income_cat.id,
                created_by_user_id=user.id,
                transaction_date=datetime(2026, 10, 5, tzinfo=UTC),
            )
        )
        await session.flush()

        resp = await client.get(
            "/api/v1/transactions/history",
            headers=auth_headers(telegram_id),
            params={
                "date_from": datetime(2026, 10, 1, tzinfo=UTC).isoformat(),
                "date_to": datetime(2026, 10, 31, tzinfo=UTC).isoformat(),
            },
        )
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert item["wallet_translation_key"] is None
        assert item["income_category_translation_key"] is None

    async def test_history_query_count_unchanged_with_translation_key_joins(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        fx = await seed_fixtures(session, budget, user)
        session.add(
            Transaction(
                family_budget_id=budget.id,
                type="income",
                wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                amount=100,
                income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                created_by_user_id=user.id,
                transaction_date=datetime(2026, 5, 1, tzinfo=UTC),
            )
        )
        await session.flush()

        statements: list[str] = []

        def record_select(
            _conn: object,
            _cursor: object,
            statement: str,
            _parameters: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement.lower())

        event.listen(engine.sync_engine, "before_cursor_execute", record_select)
        try:
            with patch(
                "app.api.v1.history.should_include_created_by",
                wraps=should_include_created_by,
            ) as include_mock:
                resp = await client.get(
                    "/api/v1/transactions/history",
                    headers=auth_headers(telegram_id),
                    params={
                        "date_from": datetime(2026, 5, 1, tzinfo=UTC).isoformat(),
                        "date_to": datetime(2026, 5, 31, tzinfo=UTC).isoformat(),
                    },
                )
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", record_select)

        assert resp.status_code == 200
        assert include_mock.await_count == 1
        history_statements = [
            statement
            for statement in statements
            if "from transactions" in statement and "join wallets" in statement
        ]
        assert len(history_statements) == 1
        assert "translation_key" in history_statements[0]

    async def test_analytics_includes_translation_keys_for_soft_deleted_categories(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)

        wallet = Wallet(family_budget_id=budget.id, name="Cash UZS", currency="UZS")
        income_cat = IncomeCategory(
            family_budget_id=budget.id,
            name="Зарплата",
            translation_key="salary",
            is_deleted=True,
            deleted_at=datetime.now(UTC),
        )
        expense_top = ExpenseCategory(
            family_budget_id=budget.id,
            name="Еда",
            translation_key="food",
        )
        session.add_all([wallet, income_cat, expense_top])
        await session.flush()
        expense_sub = ExpenseCategory(
            family_budget_id=budget.id,
            name="Продукты",
            parent_id=expense_top.id,
            translation_key="groceries",
            is_deleted=True,
            deleted_at=datetime.now(UTC),
        )
        session.add(expense_sub)
        await session.flush()

        dt = datetime(2026, 11, 1, tzinfo=UTC)
        session.add_all(
            [
                Transaction(
                    family_budget_id=budget.id,
                    type="income",
                    wallet_id=wallet.id,
                    amount=1000,
                    income_category_id=income_cat.id,
                    created_by_user_id=user.id,
                    transaction_date=dt,
                ),
                Transaction(
                    family_budget_id=budget.id,
                    type="expense",
                    wallet_id=wallet.id,
                    amount=300,
                    expense_category_id=expense_sub.id,
                    created_by_user_id=user.id,
                    transaction_date=dt,
                ),
            ]
        )
        await session.flush()

        params = {
            "currency": "UZS",
            "date_from": datetime(2026, 11, 1, tzinfo=UTC).isoformat(),
            "date_to": datetime(2026, 11, 30, tzinfo=UTC).isoformat(),
        }
        income_resp = await client.get(
            "/api/v1/analytics/income-by-category",
            headers=auth_headers(telegram_id),
            params=params,
        )
        expense_resp = await client.get(
            "/api/v1/analytics/expenses-by-category",
            headers=auth_headers(telegram_id),
            params=params,
        )
        subcategory_resp = await client.get(
            "/api/v1/analytics/expenses-by-subcategory",
            headers=auth_headers(telegram_id),
            params={**params, "parent_category_id": str(expense_top.id)},
        )

        assert income_resp.status_code == 200
        assert expense_resp.status_code == 200
        assert subcategory_resp.status_code == 200

        income_row = income_resp.json()[0]
        assert income_row["category_translation_key"] == "salary"
        assert income_row["category_name"] == "Зарплата"

        expense_row = expense_resp.json()[0]
        assert expense_row["category_translation_key"] == "food"
        assert expense_row["category_name"] == "Еда"

        subcategory_row = subcategory_resp.json()[0]
        assert subcategory_row["subcategory_translation_key"] == "groceries"
        assert subcategory_row["subcategory_name"] == "Продукты"


class TestAnalyticsExpenses:
    async def test_expenses_by_category_rolls_up_subcategories(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        fx = await seed_fixtures(session, budget, user)
        dt = datetime(2026, 2, 15, tzinfo=UTC)

        session.add_all(
            [
                Transaction(
                    family_budget_id=budget.id,
                    type="expense",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=300,
                    expense_category_id=fx["expense_sub_a"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=dt,
                ),
                Transaction(
                    family_budget_id=budget.id,
                    type="expense",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=200,
                    expense_category_id=fx["expense_sub_b"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=dt,
                ),
            ]
        )
        await session.flush()

        resp = await client.get(
            "/api/v1/analytics/expenses-by-category",
            headers=auth_headers(telegram_id),
            params={
                "currency": "UZS",
                "date_from": datetime(2026, 2, 1, tzinfo=UTC).isoformat(),
                "date_to": datetime(2026, 2, 28, tzinfo=UTC).isoformat(),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["category_name"] == "Food"
        assert data[0]["amount"] == 500

    async def test_expenses_by_category_scoped_by_currency(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        fx = await seed_fixtures(session, budget, user)
        dt = datetime(2026, 2, 15, tzinfo=UTC)

        session.add_all(
            [
                Transaction(
                    family_budget_id=budget.id,
                    type="expense",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=300,
                    expense_category_id=fx["expense_sub_a"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=dt,
                ),
                Transaction(
                    family_budget_id=budget.id,
                    type="expense",
                    wallet_id=fx["wallet_usd"].id,  # type: ignore[union-attr]
                    amount=50,
                    expense_category_id=fx["expense_sub_a"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=dt,
                ),
            ]
        )
        await session.flush()

        params = {
            "date_from": datetime(2026, 2, 1, tzinfo=UTC).isoformat(),
            "date_to": datetime(2026, 2, 28, tzinfo=UTC).isoformat(),
        }
        uzs_resp = await client.get(
            "/api/v1/analytics/expenses-by-category",
            headers=auth_headers(telegram_id),
            params={"currency": "UZS", **params},
        )
        usd_resp = await client.get(
            "/api/v1/analytics/expenses-by-category",
            headers=auth_headers(telegram_id),
            params={"currency": "USD", **params},
        )
        assert uzs_resp.status_code == 200
        assert usd_resp.status_code == 200
        assert uzs_resp.json()[0]["amount"] == 300
        assert usd_resp.json()[0]["amount"] == 50

        missing = await client.get(
            "/api/v1/analytics/expenses-by-category",
            headers=auth_headers(telegram_id),
            params=params,
        )
        assert missing.status_code == 422

    async def test_expenses_by_subcategory_drill_down(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        fx = await seed_fixtures(session, budget, user)
        dt = datetime(2026, 2, 20, tzinfo=UTC)

        session.add_all(
            [
                Transaction(
                    family_budget_id=budget.id,
                    type="expense",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=300,
                    expense_category_id=fx["expense_sub_a"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=dt,
                ),
                Transaction(
                    family_budget_id=budget.id,
                    type="expense",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=200,
                    expense_category_id=fx["expense_sub_b"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=dt,
                ),
            ]
        )
        await session.flush()

        resp = await client.get(
            "/api/v1/analytics/expenses-by-subcategory",
            headers=auth_headers(telegram_id),
            params={
                "parent_category_id": str(fx["expense_top"].id),  # type: ignore[union-attr]
                "currency": "UZS",
                "date_from": datetime(2026, 2, 1, tzinfo=UTC).isoformat(),
                "date_to": datetime(2026, 2, 28, tzinfo=UTC).isoformat(),
            },
        )
        assert resp.status_code == 200
        by_name = {row["subcategory_name"]: row["amount"] for row in resp.json()}
        assert by_name == {"Groceries": 300, "Restaurants": 200}

    async def test_expenses_by_subcategory_scoped_by_currency(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        fx = await seed_fixtures(session, budget, user)
        dt = datetime(2026, 2, 20, tzinfo=UTC)

        session.add_all(
            [
                Transaction(
                    family_budget_id=budget.id,
                    type="expense",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=300,
                    expense_category_id=fx["expense_sub_a"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=dt,
                ),
                Transaction(
                    family_budget_id=budget.id,
                    type="expense",
                    wallet_id=fx["wallet_usd"].id,  # type: ignore[union-attr]
                    amount=40,
                    expense_category_id=fx["expense_sub_a"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=dt,
                ),
            ]
        )
        await session.flush()

        params = {
            "parent_category_id": str(fx["expense_top"].id),  # type: ignore[union-attr]
            "date_from": datetime(2026, 2, 1, tzinfo=UTC).isoformat(),
            "date_to": datetime(2026, 2, 28, tzinfo=UTC).isoformat(),
        }
        uzs_resp = await client.get(
            "/api/v1/analytics/expenses-by-subcategory",
            headers=auth_headers(telegram_id),
            params={"currency": "UZS", **params},
        )
        usd_resp = await client.get(
            "/api/v1/analytics/expenses-by-subcategory",
            headers=auth_headers(telegram_id),
            params={"currency": "USD", **params},
        )
        assert uzs_resp.status_code == 200
        assert usd_resp.status_code == 200
        uzs_by_name = {row["subcategory_name"]: row["amount"] for row in uzs_resp.json()}
        usd_by_name = {row["subcategory_name"]: row["amount"] for row in usd_resp.json()}
        assert uzs_by_name == {"Groceries": 300}
        assert usd_by_name == {"Groceries": 40}

    async def test_expenses_by_subcategory_404_for_invalid_parent(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        fx = await seed_fixtures(session, budget, user)

        sub_id = str(fx["expense_sub_a"].id)  # type: ignore[union-attr]
        resp = await client.get(
            "/api/v1/analytics/expenses-by-subcategory",
            headers=auth_headers(telegram_id),
            params={"parent_category_id": sub_id, "currency": "UZS"},
        )
        assert resp.status_code == 404


class TestAnalyticsTrendAndSummary:
    async def test_trend_aggregates_last_twelve_months_and_ignores_query_params(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        fx = await seed_fixtures(session, budget, user)

        now = datetime(2026, 7, 15, tzinfo=UTC)
        session.add(
            Transaction(
                family_budget_id=budget.id,
                type="expense",
                wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                amount=500,
                expense_category_id=fx["expense_sub_a"].id,  # type: ignore[union-attr]
                created_by_user_id=user.id,
                transaction_date=datetime(2026, 7, 10, tzinfo=UTC),
            )
        )
        session.add_all(
            [
                Transaction(
                    family_budget_id=budget.id,
                    type="income",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=1000,
                    income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=datetime(2026, 7, 5, tzinfo=UTC),
                ),
                Transaction(
                    family_budget_id=budget.id,
                    type="income",
                    wallet_id=fx["wallet_usd"].id,  # type: ignore[union-attr]
                    amount=25,
                    income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=datetime(2026, 6, 5, tzinfo=UTC),
                ),
                Transaction(
                    family_budget_id=budget.id,
                    type="expense",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=999,
                    expense_category_id=fx["expense_sub_a"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=datetime(2026, 7, 10, tzinfo=UTC),
                    is_deleted=True,
                    deleted_at=datetime.now(UTC),
                ),
                Transaction(
                    family_budget_id=budget.id,
                    type="expense",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=999,
                    expense_category_id=fx["expense_sub_a"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=datetime(2020, 1, 10, tzinfo=UTC),
                ),
            ]
        )
        await session.flush()

        with patch("app.services.history_analytics.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            direct = await get_trend(session, budget.id, end=now)
            resp = await client.get(
                "/api/v1/analytics/trend",
                headers=auth_headers(telegram_id),
                params={
                    "date_from": datetime(2020, 1, 1, tzinfo=UTC).isoformat(),
                    "date_to": datetime(2020, 12, 31, tzinfo=UTC).isoformat(),
                },
            )

        assert resp.status_code == 200
        api_entries = resp.json()
        july = [e for e in api_entries if e["month"] == "2026-07" and e["currency"] == "UZS"]
        assert len(july) == 1
        assert july[0]["expense"] == 500
        assert july[0]["income"] == 1000
        assert len(api_entries) == 24
        june_usd = next(
            e for e in api_entries if e["month"] == "2026-06" and e["currency"] == "USD"
        )
        assert june_usd["income"] == 25
        empty_usd_month = next(
            e for e in api_entries if e["month"] == "2026-05" and e["currency"] == "USD"
        )
        assert empty_usd_month == {
            "month": "2026-05",
            "currency": "USD",
            "income": 0,
            "expense": 0,
        }
        direct_july = [e for e in direct if e.month == "2026-07" and e.currency == "UZS"]
        assert direct_july[0].expense == 500
        assert direct_july[0].income == 1000

    async def test_summary_transfer_net_both_directions(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        fx = await seed_fixtures(session, budget, user)
        dt = datetime(2026, 3, 5, tzinfo=UTC)

        session.add_all(
            [
                Transaction(
                    family_budget_id=budget.id,
                    type="transfer",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    to_wallet_id=fx["wallet_usd"].id,  # type: ignore[union-attr]
                    amount=100_000,
                    to_amount=8,
                    created_by_user_id=user.id,
                    transaction_date=dt,
                ),
                Transaction(
                    family_budget_id=budget.id,
                    type="transfer",
                    wallet_id=fx["wallet_usd"].id,  # type: ignore[union-attr]
                    to_wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=5,
                    to_amount=62_500,
                    created_by_user_id=user.id,
                    transaction_date=dt,
                ),
            ]
        )
        await session.flush()

        resp = await client.get(
            "/api/v1/analytics/summary",
            headers=auth_headers(telegram_id),
            params={
                "date_from": datetime(2026, 3, 1, tzinfo=UTC).isoformat(),
                "date_to": datetime(2026, 3, 31, tzinfo=UTC).isoformat(),
            },
        )
        assert resp.status_code == 200
        by_currency = {row["currency"]: row for row in resp.json()["by_currency"]}
        assert by_currency["UZS"]["transfer_net"] == -100_000 + 62_500
        assert by_currency["USD"]["transfer_net"] == 8 - 5

    async def test_average_daily_expense_uses_elapsed_days(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        fx = await seed_fixtures(session, budget, user)

        date_from = datetime(2026, 7, 1, tzinfo=UTC)
        date_to = datetime(2026, 12, 31, tzinfo=UTC)
        session.add(
            Transaction(
                family_budget_id=budget.id,
                type="expense",
                wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                amount=170,
                expense_category_id=fx["expense_sub_a"].id,  # type: ignore[union-attr]
                created_by_user_id=user.id,
                transaction_date=datetime(2026, 7, 10, tzinfo=UTC),
            )
        )
        await session.flush()

        with patch("app.services.history_analytics.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 7, 17, tzinfo=UTC)
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            resp = await client.get(
                "/api/v1/analytics/summary",
                headers=auth_headers(telegram_id),
                params={
                    "date_from": date_from.isoformat(),
                    "date_to": date_to.isoformat(),
                },
            )

        assert resp.status_code == 200
        uzs = next(row for row in resp.json()["by_currency"] if row["currency"] == "UZS")
        assert uzs["average_daily_expense"] == 170 // 17

    async def test_day_of_week_aggregation(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        fx = await seed_fixtures(session, budget, user)

        monday = datetime(2026, 3, 2, 10, 0, tzinfo=UTC)
        wednesday = datetime(2026, 3, 4, 10, 0, tzinfo=UTC)
        session.add_all(
            [
                Transaction(
                    family_budget_id=budget.id,
                    type="expense",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=100,
                    expense_category_id=fx["expense_sub_a"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=monday,
                ),
                Transaction(
                    family_budget_id=budget.id,
                    type="expense",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=50,
                    expense_category_id=fx["expense_sub_a"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=wednesday,
                ),
                Transaction(
                    family_budget_id=budget.id,
                    type="income",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=1000,
                    income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=monday,
                ),
                Transaction(
                    family_budget_id=budget.id,
                    type="income",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=500,
                    income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=wednesday,
                ),
            ]
        )
        await session.flush()

        with patch("app.services.history_analytics.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 31, tzinfo=UTC)
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            resp = await client.get(
                "/api/v1/analytics/summary",
                headers=auth_headers(telegram_id),
                params={
                    "date_from": datetime(2026, 3, 1, tzinfo=UTC).isoformat(),
                    "date_to": datetime(2026, 3, 31, tzinfo=UTC).isoformat(),
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        expense_dow = body["day_of_week_expense"]["UZS"]
        income_dow = body["day_of_week_income"]["UZS"]
        assert expense_dow[0] == 100 // 5
        assert expense_dow[2] == 50 // 4
        assert income_dow[0] == 1000
        assert income_dow[2] == 500

    async def test_summary_aggregates_totals_and_weekdays_in_sql(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        _client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        fx = await seed_fixtures(session, budget, user)
        session.add_all(
            [
                Transaction(
                    family_budget_id=budget.id,
                    type="income",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=1000,
                    income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=datetime(2026, 3, 2, tzinfo=UTC),
                ),
                Transaction(
                    family_budget_id=budget.id,
                    type="expense",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=250,
                    expense_category_id=fx["expense_sub_a"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=datetime(2026, 3, 4, tzinfo=UTC),
                ),
                Transaction(
                    family_budget_id=budget.id,
                    type="transfer",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    to_wallet_id=fx["wallet_usd"].id,  # type: ignore[union-attr]
                    amount=100_000,
                    to_amount=8,
                    created_by_user_id=user.id,
                    transaction_date=datetime(2026, 3, 5, tzinfo=UTC),
                ),
                Transaction(
                    family_budget_id=budget.id,
                    type="income",
                    wallet_id=fx["wallet_usd"].id,  # type: ignore[union-attr]
                    amount=75,
                    income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=datetime(2026, 3, 8, 23, 30, tzinfo=UTC),
                ),
            ]
        )
        await session.flush()

        statements: list[str] = []

        def record_select(
            _conn: object,
            _cursor: object,
            statement: str,
            _parameters: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement.lower())

        event.listen(engine.sync_engine, "before_cursor_execute", record_select)
        try:
            summary = await get_summary(
                session,
                budget.id,
                datetime(2026, 3, 1, tzinfo=UTC),
                datetime(2026, 3, 31, 23, 59, 59, tzinfo=UTC),
                now=datetime(2026, 3, 31, tzinfo=UTC),
            )
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", record_select)

        by_currency = {row.currency: row for row in summary.by_currency}
        assert by_currency["UZS"].income == 1000
        assert by_currency["UZS"].expense == 250
        assert by_currency["UZS"].transfer_net == -100_000
        assert by_currency["USD"].income == 75
        assert by_currency["USD"].transfer_net == 8
        assert summary.day_of_week_income["UZS"][0] == 1000
        assert summary.day_of_week_expense["UZS"][2] == 250 // 4
        assert summary.day_of_week_income["USD"][6] == 75
        uzs_summary = by_currency["UZS"]
        assert uzs_summary.most_expensive_weekday == 2
        assert uzs_summary.most_expensive_weekday_average == 250 // 4
        assert len(statements) == 2
        assert all("group by" in statement for statement in statements)
        assert "union all" in statements[0]
        assert "extract(isodow from timezone(" in statements[1]

    async def test_analytics_defaults_to_calendar_year(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        fx = await seed_fixtures(session, budget, user)

        session.add(
            Transaction(
                family_budget_id=budget.id,
                type="income",
                wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                amount=777,
                income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                created_by_user_id=user.id,
                transaction_date=datetime(2026, 8, 1, tzinfo=UTC),
            )
        )
        session.add(
            Transaction(
                family_budget_id=budget.id,
                type="income",
                wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                amount=111,
                income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                created_by_user_id=user.id,
                transaction_date=datetime(2025, 8, 1, tzinfo=UTC),
            )
        )
        await session.flush()

        with patch("app.services.history_analytics.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 8, 15, tzinfo=UTC)
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            resp = await client.get(
                "/api/v1/analytics/income-by-category",
                headers=auth_headers(telegram_id),
                params={"currency": "UZS"},
            )

        assert resp.status_code == 200
        assert resp.json()[0]["amount"] == 777
        date_from, date_to = default_calendar_year_range(datetime(2026, 8, 15, tzinfo=UTC))
        assert date_from.year == 2026
        assert date_to.year == 2026

    async def test_income_by_category_scoped_by_currency(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        fx = await seed_fixtures(session, budget, user)
        dt = datetime(2026, 8, 1, tzinfo=UTC)

        session.add_all(
            [
                Transaction(
                    family_budget_id=budget.id,
                    type="income",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=1000,
                    income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=dt,
                ),
                Transaction(
                    family_budget_id=budget.id,
                    type="income",
                    wallet_id=fx["wallet_usd"].id,  # type: ignore[union-attr]
                    amount=25,
                    income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=dt,
                ),
            ]
        )
        await session.flush()

        params = {
            "date_from": datetime(2026, 8, 1, tzinfo=UTC).isoformat(),
            "date_to": datetime(2026, 8, 31, tzinfo=UTC).isoformat(),
        }
        uzs_resp = await client.get(
            "/api/v1/analytics/income-by-category",
            headers=auth_headers(telegram_id),
            params={"currency": "UZS", **params},
        )
        usd_resp = await client.get(
            "/api/v1/analytics/income-by-category",
            headers=auth_headers(telegram_id),
            params={"currency": "USD", **params},
        )
        assert uzs_resp.status_code == 200
        assert usd_resp.status_code == 200
        assert uzs_resp.json()[0]["amount"] == 1000
        assert usd_resp.json()[0]["amount"] == 25

        invalid = await client.get(
            "/api/v1/analytics/income-by-category",
            headers=auth_headers(telegram_id),
            params={"currency": "EUR", **params},
        )
        assert invalid.status_code == 422


class TestMemberReadAccess:
    async def test_member_can_read_all_history_and_analytics_endpoints(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        member_tid = owner_tid + 1
        owner, budget = await create_user_with_budget(session, telegram_id=owner_tid)
        member = User(
            telegram_id=member_tid,
            family_budget_id=budget.id,
            role="member",
            language="ru",
        )
        session.add(member)
        await session.flush()
        fx = await seed_fixtures(session, budget, owner)
        dt = datetime(2026, 9, 1, tzinfo=UTC)

        session.add(
            Transaction(
                family_budget_id=budget.id,
                type="expense",
                wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                amount=100,
                expense_category_id=fx["expense_sub_a"].id,  # type: ignore[union-attr]
                created_by_user_id=owner.id,
                transaction_date=dt,
            )
        )
        await session.flush()

        headers = auth_headers(member_tid)
        params = {
            "currency": "UZS",
            "date_from": datetime(2026, 9, 1, tzinfo=UTC).isoformat(),
            "date_to": datetime(2026, 9, 30, tzinfo=UTC).isoformat(),
        }

        endpoints = [
            ("/api/v1/transactions/history", params),
            ("/api/v1/analytics/expenses-by-category", params),
            (
                "/api/v1/analytics/expenses-by-subcategory",
                {**params, "parent_category_id": str(fx["expense_top"].id)},  # type: ignore[union-attr]
            ),
            ("/api/v1/analytics/income-by-category", params),
            ("/api/v1/analytics/trend", {}),
            ("/api/v1/analytics/summary", params),
            ("/api/v1/analytics/wallet-balances", {}),
        ]

        for path, query in endpoints:
            resp = await client.get(path, headers=headers, params=query)
            assert resp.status_code == 200, f"{path} returned {resp.status_code}: {resp.text}"


class TestWalletBalances:
    async def test_returns_both_currencies_in_fixed_order(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        await create_user_with_budget(session, telegram_id=telegram_id)

        resp = await client.get(
            "/api/v1/analytics/wallet-balances",
            headers=auth_headers(telegram_id),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert list(body.keys()) == ["balances"]
        assert len(body["balances"]) == 2
        assert body["balances"][0]["currency"] == "UZS"
        assert body["balances"][1]["currency"] == "USD"
        assert body["balances"][0]["balance"] == 0
        assert body["balances"][1]["balance"] == 0

    async def test_balance_formula_all_time_no_date_filtering(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        fx = await seed_fixtures(session, budget, user)

        session.add_all(
            [
                Transaction(
                    family_budget_id=budget.id,
                    type="income",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=5000,
                    income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=datetime(2019, 1, 1, tzinfo=UTC),
                ),
                Transaction(
                    family_budget_id=budget.id,
                    type="expense",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=1200,
                    expense_category_id=fx["expense_sub_a"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=datetime(2030, 12, 31, tzinfo=UTC),
                ),
                Transaction(
                    family_budget_id=budget.id,
                    type="income",
                    wallet_id=fx["wallet_usd"].id,  # type: ignore[union-attr]
                    amount=100,
                    income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=datetime(2020, 6, 15, tzinfo=UTC),
                ),
            ]
        )
        await session.flush()

        resp = await client.get(
            "/api/v1/analytics/wallet-balances",
            headers=auth_headers(telegram_id),
        )
        assert resp.status_code == 200
        by_currency = {row["currency"]: row["balance"] for row in resp.json()["balances"]}
        assert by_currency["UZS"] == 5000 - 1200
        assert by_currency["USD"] == 100

    async def test_soft_deleted_wallet_transactions_included(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        fx = await seed_fixtures(session, budget, user)

        deleted_wallet = Wallet(
            family_budget_id=budget.id,
            name="Old Cash",
            currency="UZS",
            is_deleted=True,
            deleted_at=datetime.now(UTC),
        )
        session.add(deleted_wallet)
        await session.flush()

        session.add(
            Transaction(
                family_budget_id=budget.id,
                type="income",
                wallet_id=deleted_wallet.id,
                amount=2500,
                income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                created_by_user_id=user.id,
                transaction_date=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        await session.flush()

        resp = await client.get(
            "/api/v1/analytics/wallet-balances",
            headers=auth_headers(telegram_id),
        )
        assert resp.status_code == 200
        uzs = next(row for row in resp.json()["balances"] if row["currency"] == "UZS")
        assert uzs["balance"] == 2500

    async def test_soft_deleted_transactions_excluded(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        fx = await seed_fixtures(session, budget, user)
        dt = datetime(2026, 2, 1, tzinfo=UTC)

        session.add_all(
            [
                Transaction(
                    family_budget_id=budget.id,
                    type="income",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=800,
                    income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=dt,
                ),
                Transaction(
                    family_budget_id=budget.id,
                    type="income",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=9999,
                    income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=dt,
                    is_deleted=True,
                    deleted_at=datetime.now(UTC),
                ),
            ]
        )
        await session.flush()

        resp = await client.get(
            "/api/v1/analytics/wallet-balances",
            headers=auth_headers(telegram_id),
        )
        assert resp.status_code == 200
        uzs = next(row for row in resp.json()["balances"] if row["currency"] == "UZS")
        assert uzs["balance"] == 800

    async def test_same_currency_transfer_nets_to_zero(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        fx = await seed_fixtures(session, budget, user)

        wallet_uzs_b = Wallet(family_budget_id=budget.id, name="Savings UZS", currency="UZS")
        session.add(wallet_uzs_b)
        await session.flush()

        dt = datetime(2026, 3, 1, tzinfo=UTC)
        session.add_all(
            [
                Transaction(
                    family_budget_id=budget.id,
                    type="income",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=10_000,
                    income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=dt,
                ),
                Transaction(
                    family_budget_id=budget.id,
                    type="transfer",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    to_wallet_id=wallet_uzs_b.id,
                    amount=3000,
                    to_amount=3000,
                    created_by_user_id=user.id,
                    transaction_date=dt,
                ),
            ]
        )
        await session.flush()

        resp = await client.get(
            "/api/v1/analytics/wallet-balances",
            headers=auth_headers(telegram_id),
        )
        assert resp.status_code == 200
        uzs = next(row for row in resp.json()["balances"] if row["currency"] == "UZS")
        assert uzs["balance"] == 10_000

    async def test_cross_currency_transfer_moves_amounts(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        fx = await seed_fixtures(session, budget, user)
        dt = datetime(2026, 4, 1, tzinfo=UTC)

        session.add_all(
            [
                Transaction(
                    family_budget_id=budget.id,
                    type="income",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=200_000,
                    income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=dt,
                ),
                Transaction(
                    family_budget_id=budget.id,
                    type="income",
                    wallet_id=fx["wallet_usd"].id,  # type: ignore[union-attr]
                    amount=50,
                    income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                    created_by_user_id=user.id,
                    transaction_date=dt,
                ),
                Transaction(
                    family_budget_id=budget.id,
                    type="transfer",
                    wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    to_wallet_id=fx["wallet_usd"].id,  # type: ignore[union-attr]
                    amount=100_000,
                    to_amount=8,
                    created_by_user_id=user.id,
                    transaction_date=dt,
                ),
                Transaction(
                    family_budget_id=budget.id,
                    type="transfer",
                    wallet_id=fx["wallet_usd"].id,  # type: ignore[union-attr]
                    to_wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                    amount=5,
                    to_amount=62_500,
                    created_by_user_id=user.id,
                    transaction_date=dt,
                ),
            ]
        )
        await session.flush()

        resp = await client.get(
            "/api/v1/analytics/wallet-balances",
            headers=auth_headers(telegram_id),
        )
        assert resp.status_code == 200
        by_currency = {row["currency"]: row["balance"] for row in resp.json()["balances"]}
        assert by_currency["UZS"] == 200_000 - 100_000 + 62_500
        assert by_currency["USD"] == 50 + 8 - 5

    async def test_zero_wallets_of_currency_returns_zero_balance(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)

        wallet_uzs_only = Wallet(family_budget_id=budget.id, name="Only UZS", currency="UZS")
        income_cat = IncomeCategory(family_budget_id=budget.id, name="Salary")
        session.add_all([wallet_uzs_only, income_cat])
        await session.flush()

        session.add(
            Transaction(
                family_budget_id=budget.id,
                type="income",
                wallet_id=wallet_uzs_only.id,
                amount=1500,
                income_category_id=income_cat.id,
                created_by_user_id=user.id,
                transaction_date=datetime(2026, 5, 1, tzinfo=UTC),
            )
        )
        await session.flush()

        resp = await client.get(
            "/api/v1/analytics/wallet-balances",
            headers=auth_headers(telegram_id),
        )
        assert resp.status_code == 200
        body = resp.json()["balances"]
        assert len(body) == 2
        assert body[0] == {"currency": "UZS", "balance": 1500}
        assert body[1] == {"currency": "USD", "balance": 0}

    async def test_member_has_read_access(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        member_tid = owner_tid + 1
        owner, budget = await create_user_with_budget(session, telegram_id=owner_tid)
        member = User(
            telegram_id=member_tid,
            family_budget_id=budget.id,
            role="member",
            language="ru",
        )
        session.add(member)
        await session.flush()
        fx = await seed_fixtures(session, budget, owner)
        session.add(
            Transaction(
                family_budget_id=budget.id,
                type="income",
                wallet_id=fx["wallet_uzs"].id,  # type: ignore[union-attr]
                amount=400,
                income_category_id=fx["income_cat"].id,  # type: ignore[union-attr]
                created_by_user_id=owner.id,
                transaction_date=datetime(2026, 6, 1, tzinfo=UTC),
            )
        )
        await session.flush()

        resp = await client.get(
            "/api/v1/analytics/wallet-balances",
            headers=auth_headers(member_tid),
        )
        assert resp.status_code == 200
        uzs = next(row for row in resp.json()["balances"] if row["currency"] == "UZS")
        assert uzs["balance"] == 400
