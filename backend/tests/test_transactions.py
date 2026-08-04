import socket
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine, get_session
from app.main import app
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
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
    return bearer_header_for_telegram_id(telegram_id)


def txn_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "transaction_date": datetime.now(UTC).isoformat(),
        "amount": 100,
    }
    base.update(overrides)
    return base


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


async def seed_income_fixtures(
    session: AsyncSession, budget: FamilyBudget, user: User
) -> tuple[Wallet, IncomeCategory]:
    wallet = Wallet(family_budget_id=budget.id, name="Cash UZS", currency="UZS")
    category = IncomeCategory(family_budget_id=budget.id, name="Salary")
    session.add_all([wallet, category])
    await session.flush()
    return wallet, category


async def seed_expense_fixtures(
    session: AsyncSession, budget: FamilyBudget
) -> tuple[Wallet, ExpenseCategory, ExpenseCategory]:
    wallet = Wallet(family_budget_id=budget.id, name="Cash UZS", currency="UZS")
    top = ExpenseCategory(family_budget_id=budget.id, name="Food")
    session.add_all([wallet, top])
    await session.flush()
    sub = ExpenseCategory(family_budget_id=budget.id, name="Groceries", parent_id=top.id)
    session.add(sub)
    await session.flush()
    return wallet, top, sub


class TestAllEndpointsImplemented:
    async def test_owner_and_member_can_create_and_read_all_types(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        member_tid = owner_tid + 1
        owner, budget = await create_user_with_budget(session, telegram_id=owner_tid, role="owner")
        member = User(
            telegram_id=member_tid,
            family_budget_id=budget.id,
            role="member",
            language="ru",
        )
        session.add(member)
        await session.flush()

        wallet_uzs = Wallet(family_budget_id=budget.id, name="UZS", currency="UZS")
        wallet_usd = Wallet(family_budget_id=budget.id, name="USD", currency="USD")
        income_cat = IncomeCategory(family_budget_id=budget.id, name="Salary")
        top = ExpenseCategory(family_budget_id=budget.id, name="Food")
        session.add_all([wallet_uzs, wallet_usd, income_cat, top])
        await session.flush()
        sub = ExpenseCategory(family_budget_id=budget.id, name="Groceries", parent_id=top.id)
        session.add(sub)
        await session.flush()

        for telegram_id in (owner_tid, member_tid):
            headers = auth_headers(telegram_id)
            income_resp = await client.post(
                "/api/v1/transactions/income",
                headers=headers,
                json=txn_payload(wallet_id=str(wallet_uzs.id), income_category_id=str(income_cat.id)),
            )
            assert income_resp.status_code == 201, income_resp.text
            assert income_resp.json()["type"] == "income"

            expense_resp = await client.post(
                "/api/v1/transactions/expense",
                headers=headers,
                json=txn_payload(wallet_id=str(wallet_uzs.id), expense_category_id=str(sub.id)),
            )
            assert expense_resp.status_code == 201, expense_resp.text
            assert expense_resp.json()["type"] == "expense"

            transfer_resp = await client.post(
                "/api/v1/transactions/transfer",
                headers=headers,
                json=txn_payload(
                    wallet_id=str(wallet_uzs.id),
                    to_wallet_id=str(wallet_usd.id),
                    amount=1000,
                    rate=12500,
                ),
            )
            assert transfer_resp.status_code == 201, transfer_resp.text
            transfer = transfer_resp.json()
            assert transfer["type"] == "transfer"
            assert transfer["to_amount"] == 0

            get_resp = await client.get(
                f"/api/v1/transactions/{income_resp.json()['id']}",
                headers=headers,
            )
            assert get_resp.status_code == 200


class TestIncomeExpenseValidation:
    async def test_income_validates_wallet_and_category_not_deleted(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        wallet, category = await seed_income_fixtures(session, budget, user)
        headers = auth_headers(telegram_id)

        ok = await client.post(
            "/api/v1/transactions/income",
            headers=headers,
            json=txn_payload(wallet_id=str(wallet.id), income_category_id=str(category.id)),
        )
        assert ok.status_code == 201

        deleted_wallet = Wallet(
            family_budget_id=budget.id,
            name="Deleted",
            currency="UZS",
            is_deleted=True,
            deleted_at=datetime.now(UTC),
        )
        session.add(deleted_wallet)
        await session.flush()
        assert (
            await client.post(
                "/api/v1/transactions/income",
                headers=headers,
                json=txn_payload(
                    wallet_id=str(deleted_wallet.id),
                    income_category_id=str(category.id),
                ),
            )
        ).status_code == 404

        deleted_category = IncomeCategory(
            family_budget_id=budget.id,
            name="Deleted cat",
            is_deleted=True,
            deleted_at=datetime.now(UTC),
        )
        session.add(deleted_category)
        await session.flush()
        assert (
            await client.post(
                "/api/v1/transactions/income",
                headers=headers,
                json=txn_payload(
                    wallet_id=str(wallet.id),
                    income_category_id=str(deleted_category.id),
                ),
            )
        ).status_code == 404

    async def test_expense_validates_wallet_and_category_not_deleted(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        wallet, top, sub = await seed_expense_fixtures(session, budget)
        headers = auth_headers(telegram_id)

        ok = await client.post(
            "/api/v1/transactions/expense",
            headers=headers,
            json=txn_payload(wallet_id=str(wallet.id), expense_category_id=str(sub.id)),
        )
        assert ok.status_code == 201

        deleted_wallet = Wallet(
            family_budget_id=budget.id,
            name="Deleted",
            currency="UZS",
            is_deleted=True,
            deleted_at=datetime.now(UTC),
        )
        session.add(deleted_wallet)
        await session.flush()
        assert (
            await client.post(
                "/api/v1/transactions/expense",
                headers=headers,
                json=txn_payload(
                    wallet_id=str(deleted_wallet.id),
                    expense_category_id=str(sub.id),
                ),
            )
        ).status_code == 404

        deleted_subcategory = ExpenseCategory(
            family_budget_id=budget.id,
            name="Deleted sub",
            parent_id=top.id,
            is_deleted=True,
            deleted_at=datetime.now(UTC),
        )
        session.add(deleted_subcategory)
        await session.flush()
        assert (
            await client.post(
                "/api/v1/transactions/expense",
                headers=headers,
                json=txn_payload(
                    wallet_id=str(wallet.id),
                    expense_category_id=str(deleted_subcategory.id),
                ),
            )
        ).status_code == 404

    async def test_expense_accepts_top_level_category_with_201(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        wallet, top, _ = await seed_expense_fixtures(session, budget)
        headers = auth_headers(telegram_id)

        response = await client.post(
            "/api/v1/transactions/expense",
            headers=headers,
            json=txn_payload(wallet_id=str(wallet.id), expense_category_id=str(top.id)),
        )
        assert response.status_code == 201
        assert response.json()["expense_category_id"] == str(top.id)


class TestCommentMaxLength:
    async def test_income_rejects_comment_over_200_chars(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        wallet, category = await seed_income_fixtures(session, budget, user)
        headers = auth_headers(telegram_id)

        response = await client.post(
            "/api/v1/transactions/income",
            headers=headers,
            json=txn_payload(
                wallet_id=str(wallet.id),
                income_category_id=str(category.id),
                comment="x" * 201,
            ),
        )
        assert response.status_code == 422

    async def test_income_accepts_comment_of_200_chars(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        wallet, category = await seed_income_fixtures(session, budget, user)
        headers = auth_headers(telegram_id)
        comment = "x" * 200

        response = await client.post(
            "/api/v1/transactions/income",
            headers=headers,
            json=txn_payload(
                wallet_id=str(wallet.id),
                income_category_id=str(category.id),
                comment=comment,
            ),
        )
        assert response.status_code == 201
        assert response.json()["comment"] == comment

    async def test_expense_rejects_comment_over_200_chars(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        wallet, _, sub = await seed_expense_fixtures(session, budget)
        headers = auth_headers(telegram_id)

        response = await client.post(
            "/api/v1/transactions/expense",
            headers=headers,
            json=txn_payload(
                wallet_id=str(wallet.id),
                expense_category_id=str(sub.id),
                comment="x" * 201,
            ),
        )
        assert response.status_code == 422

    async def test_expense_accepts_comment_of_200_chars(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        wallet, _, sub = await seed_expense_fixtures(session, budget)
        headers = auth_headers(telegram_id)
        comment = "x" * 200

        response = await client.post(
            "/api/v1/transactions/expense",
            headers=headers,
            json=txn_payload(
                wallet_id=str(wallet.id),
                expense_category_id=str(sub.id),
                comment=comment,
            ),
        )
        assert response.status_code == 201
        assert response.json()["comment"] == comment

    async def test_transfer_rejects_comment_over_200_chars(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        wallet_a = Wallet(family_budget_id=budget.id, name="Cash", currency="UZS")
        wallet_b = Wallet(family_budget_id=budget.id, name="Card", currency="UZS")
        session.add_all([wallet_a, wallet_b])
        await session.flush()
        headers = auth_headers(telegram_id)

        response = await client.post(
            "/api/v1/transactions/transfer",
            headers=headers,
            json=txn_payload(
                wallet_id=str(wallet_a.id),
                to_wallet_id=str(wallet_b.id),
                comment="x" * 201,
            ),
        )
        assert response.status_code == 422

    async def test_transfer_accepts_comment_of_200_chars(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        wallet_a = Wallet(family_budget_id=budget.id, name="Cash", currency="UZS")
        wallet_b = Wallet(family_budget_id=budget.id, name="Card", currency="UZS")
        session.add_all([wallet_a, wallet_b])
        await session.flush()
        headers = auth_headers(telegram_id)
        comment = "x" * 200

        response = await client.post(
            "/api/v1/transactions/transfer",
            headers=headers,
            json=txn_payload(
                wallet_id=str(wallet_a.id),
                to_wallet_id=str(wallet_b.id),
                comment=comment,
            ),
        )
        assert response.status_code == 201
        assert response.json()["comment"] == comment


class TestTransferValidation:
    async def test_same_currency_transfer_sets_to_amount_without_rate(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        wallet_a = Wallet(family_budget_id=budget.id, name="Cash", currency="UZS")
        wallet_b = Wallet(family_budget_id=budget.id, name="Card", currency="UZS")
        session.add_all([wallet_a, wallet_b])
        await session.flush()
        headers = auth_headers(telegram_id)

        ok = await client.post(
            "/api/v1/transactions/transfer",
            headers=headers,
            json=txn_payload(
                wallet_id=str(wallet_a.id),
                to_wallet_id=str(wallet_b.id),
                amount=500,
            ),
        )
        assert ok.status_code == 201
        body = ok.json()
        assert body["to_amount"] == 500
        assert body["rate"] is None

        with_rate = await client.post(
            "/api/v1/transactions/transfer",
            headers=headers,
            json=txn_payload(
                wallet_id=str(wallet_a.id),
                to_wallet_id=str(wallet_b.id),
                amount=500,
                rate=12500,
            ),
        )
        assert with_rate.status_code == 422

    async def test_different_currency_transfer_requires_rate_and_rounds_to_amount(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        wallet_uzs = Wallet(family_budget_id=budget.id, name="UZS", currency="UZS")
        wallet_usd = Wallet(family_budget_id=budget.id, name="USD", currency="USD")
        session.add_all([wallet_uzs, wallet_usd])
        await session.flush()
        headers = auth_headers(telegram_id)

        no_rate = await client.post(
            "/api/v1/transactions/transfer",
            headers=headers,
            json=txn_payload(
                wallet_id=str(wallet_uzs.id),
                to_wallet_id=str(wallet_usd.id),
                amount=100_000,
            ),
        )
        assert no_rate.status_code == 422

        uzs_to_usd = await client.post(
            "/api/v1/transactions/transfer",
            headers=headers,
            json=txn_payload(
                wallet_id=str(wallet_uzs.id),
                to_wallet_id=str(wallet_usd.id),
                amount=100_000,
                rate=12_500,
            ),
        )
        assert uzs_to_usd.status_code == 201
        assert uzs_to_usd.json()["to_amount"] == round(100_000 / 12_500)

        usd_to_uzs = await client.post(
            "/api/v1/transactions/transfer",
            headers=headers,
            json=txn_payload(
                wallet_id=str(wallet_usd.id),
                to_wallet_id=str(wallet_uzs.id),
                amount=10,
                rate=12_500,
            ),
        )
        assert usd_to_uzs.status_code == 201
        assert usd_to_uzs.json()["to_amount"] == round(10 * 12_500)

        zero_rate = await client.post(
            "/api/v1/transactions/transfer",
            headers=headers,
            json=txn_payload(
                wallet_id=str(wallet_uzs.id),
                to_wallet_id=str(wallet_usd.id),
                amount=100,
                rate=0,
            ),
        )
        assert zero_rate.status_code == 422

    async def test_transfer_rejects_same_wallet_with_400(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        wallet = Wallet(family_budget_id=budget.id, name="Cash", currency="UZS")
        session.add(wallet)
        await session.flush()
        headers = auth_headers(telegram_id)

        response = await client.post(
            "/api/v1/transactions/transfer",
            headers=headers,
            json=txn_payload(wallet_id=str(wallet.id), to_wallet_id=str(wallet.id), amount=100),
        )
        assert response.status_code == 400

    async def test_transfer_rejects_category_fields_with_422(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        _, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        wallet_a = Wallet(family_budget_id=budget.id, name="A", currency="UZS")
        wallet_b = Wallet(family_budget_id=budget.id, name="B", currency="UZS")
        session.add_all([wallet_a, wallet_b])
        await session.flush()
        headers = auth_headers(telegram_id)
        base = txn_payload(
            wallet_id=str(wallet_a.id),
            to_wallet_id=str(wallet_b.id),
            amount=100,
        )

        with_income = await client.post(
            "/api/v1/transactions/transfer",
            headers=headers,
            json={**base, "income_category_id": str(uuid.uuid4())},
        )
        assert with_income.status_code == 422

        with_expense = await client.post(
            "/api/v1/transactions/transfer",
            headers=headers,
            json={**base, "expense_category_id": str(uuid.uuid4())},
        )
        assert with_expense.status_code == 422


class TestEditDeletePermissions:
    async def test_member_can_edit_and_delete_others_shared_transactions(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        member_tid = owner_tid + 1
        owner, budget = await create_user_with_budget(session, telegram_id=owner_tid, role="owner")
        member = User(
            telegram_id=member_tid,
            family_budget_id=budget.id,
            role="member",
            language="ru",
        )
        session.add(member)
        wallet, category = await seed_income_fixtures(session, budget, owner)
        await session.flush()

        owner_txn = Transaction(
            family_budget_id=budget.id,
            type="income",
            wallet_id=wallet.id,
            amount=100,
            income_category_id=category.id,
            created_by_user_id=owner.id,
            transaction_date=datetime.now(UTC),
        )
        member_txn = Transaction(
            family_budget_id=budget.id,
            type="income",
            wallet_id=wallet.id,
            amount=200,
            income_category_id=category.id,
            created_by_user_id=member.id,
            transaction_date=datetime.now(UTC),
        )
        session.add_all([owner_txn, member_txn])
        await session.flush()

        member_headers = auth_headers(member_tid)
        patch_body = txn_payload(
            wallet_id=str(wallet.id),
            income_category_id=str(category.id),
            amount=250,
        )

        owner_patch = await client.patch(
            f"/api/v1/transactions/{owner_txn.id}",
            headers=member_headers,
            json=patch_body,
        )
        assert owner_patch.status_code == 200
        assert owner_patch.json()["amount"] == 250
        assert owner_patch.json()["created_by_user_id"] == str(owner.id)

        owner_delete = await client.delete(
            f"/api/v1/transactions/{owner_txn.id}",
            headers=member_headers,
        )
        assert owner_delete.status_code == 200
        assert owner_delete.json()["id"] == str(owner_txn.id)

        own_patch = await client.patch(
            f"/api/v1/transactions/{member_txn.id}",
            headers=member_headers,
            json=patch_body,
        )
        assert own_patch.status_code == 200
        assert own_patch.json()["amount"] == 250

        own_delete = await client.delete(
            f"/api/v1/transactions/{member_txn.id}",
            headers=member_headers,
        )
        assert own_delete.status_code == 200
        assert own_delete.json()["id"] == str(member_txn.id)

    async def test_owner_can_patch_and_delete_any_transaction(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        member_tid = owner_tid + 1
        owner, budget = await create_user_with_budget(session, telegram_id=owner_tid, role="owner")
        member = User(
            telegram_id=member_tid,
            family_budget_id=budget.id,
            role="member",
            language="ru",
        )
        session.add(member)
        wallet, category = await seed_income_fixtures(session, budget, owner)
        await session.flush()

        member_txn = Transaction(
            family_budget_id=budget.id,
            type="income",
            wallet_id=wallet.id,
            amount=300,
            income_category_id=category.id,
            created_by_user_id=member.id,
            transaction_date=datetime.now(UTC),
        )
        session.add(member_txn)
        await session.flush()
        headers = auth_headers(owner_tid)
        patch_body = txn_payload(
            wallet_id=str(wallet.id),
            income_category_id=str(category.id),
            amount=350,
        )

        patch_resp = await client.patch(
            f"/api/v1/transactions/{member_txn.id}",
            headers=headers,
            json=patch_body,
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["amount"] == 350

        delete_resp = await client.delete(
            f"/api/v1/transactions/{member_txn.id}",
            headers=headers,
        )
        assert delete_resp.status_code == 200


class TestCrossFamilyAccess:
    async def test_cross_family_transaction_access_returns_404(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        other_tid = owner_tid + 1
        owner, budget = await create_user_with_budget(session, telegram_id=owner_tid, role="owner")
        await create_user_with_budget(session, telegram_id=other_tid, role="owner")
        wallet, category = await seed_income_fixtures(session, budget, owner)
        txn = Transaction(
            family_budget_id=budget.id,
            type="income",
            wallet_id=wallet.id,
            amount=100,
            income_category_id=category.id,
            created_by_user_id=owner.id,
            transaction_date=datetime.now(UTC),
        )
        session.add(txn)
        await session.flush()
        headers = auth_headers(other_tid)

        assert (
            await client.get(f"/api/v1/transactions/{txn.id}", headers=headers)
        ).status_code == 404
        assert (
            await client.patch(
                f"/api/v1/transactions/{txn.id}",
                headers=headers,
                json=txn_payload(
                    wallet_id=str(wallet.id),
                    income_category_id=str(category.id),
                ),
            )
        ).status_code == 404
        assert (
            await client.delete(f"/api/v1/transactions/{txn.id}", headers=headers)
        ).status_code == 404


class TestSoftDelete:
    async def test_delete_performs_soft_delete_without_cascade(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        wallet, category = await seed_income_fixtures(session, budget, user)
        txn = Transaction(
            family_budget_id=budget.id,
            type="income",
            wallet_id=wallet.id,
            amount=100,
            income_category_id=category.id,
            created_by_user_id=user.id,
            transaction_date=datetime.now(UTC),
        )
        session.add(txn)
        await session.flush()
        headers = auth_headers(telegram_id)

        delete_resp = await client.delete(f"/api/v1/transactions/{txn.id}", headers=headers)
        assert delete_resp.status_code == 200

        await session.refresh(txn)
        assert txn.is_deleted is True
        assert txn.deleted_at is not None
        assert txn.income_category_id == category.id
        assert txn.wallet_id == wallet.id

        assert (
            await client.get(f"/api/v1/transactions/{txn.id}", headers=headers)
        ).status_code == 404
