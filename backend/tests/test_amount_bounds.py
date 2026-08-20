import socket
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine, get_session
from app.main import app
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.transactions import MAX_AMOUNT
from tests.auth_helpers import TEST_APP_PASS_SECRET, bearer_header_for_telegram_id


def _db_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            return True
    except OSError:
        return False


async def _reset_engine() -> None:
    await engine.dispose()


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


def _random_tid() -> int:
    return int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000


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
    session: AsyncSession, budget: FamilyBudget
) -> tuple[Wallet, IncomeCategory]:
    wallet = Wallet(family_budget_id=budget.id, name="Cash UZS", currency="UZS")
    category = IncomeCategory(family_budget_id=budget.id, name="Salary")
    session.add_all([wallet, category])
    await session.flush()
    return wallet, category


async def seed_expense_fixtures(
    session: AsyncSession, budget: FamilyBudget
) -> tuple[Wallet, ExpenseCategory]:
    wallet = Wallet(family_budget_id=budget.id, name="Cash UZS", currency="UZS")
    category = ExpenseCategory(family_budget_id=budget.id, name="Food")
    session.add_all([wallet, category])
    await session.flush()
    return wallet, category


async def _count_transactions(session: AsyncSession, budget_id: uuid.UUID) -> int:
    result = await session.execute(
        select(Transaction).where(Transaction.family_budget_id == budget_id)
    )
    return len(result.scalars().all())


class TestAmountUpperBound:
    async def test_income_amount_over_cap_rejected_with_422(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = _random_tid()
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        wallet, category = await seed_income_fixtures(session, budget)

        resp = await client.post(
            "/api/v1/transactions/income",
            headers=auth_headers(telegram_id),
            json=txn_payload(
                wallet_id=str(wallet.id),
                income_category_id=str(category.id),
                amount=MAX_AMOUNT + 1,
            ),
        )
        assert resp.status_code == 422, resp.text
        assert await _count_transactions(session, budget.id) == 0

    async def test_expense_amount_over_cap_rejected_with_422(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = _random_tid()
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        wallet, category = await seed_expense_fixtures(session, budget)

        resp = await client.post(
            "/api/v1/transactions/expense",
            headers=auth_headers(telegram_id),
            json=txn_payload(
                wallet_id=str(wallet.id),
                expense_category_id=str(category.id),
                amount=MAX_AMOUNT + 1,
            ),
        )
        assert resp.status_code == 422, resp.text
        assert await _count_transactions(session, budget.id) == 0

    async def test_transfer_amount_over_cap_rejected_with_422(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = _random_tid()
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        wallet_a = Wallet(family_budget_id=budget.id, name="A", currency="UZS")
        wallet_b = Wallet(family_budget_id=budget.id, name="B", currency="UZS")
        session.add_all([wallet_a, wallet_b])
        await session.flush()

        resp = await client.post(
            "/api/v1/transactions/transfer",
            headers=auth_headers(telegram_id),
            json=txn_payload(
                wallet_id=str(wallet_a.id),
                to_wallet_id=str(wallet_b.id),
                amount=MAX_AMOUNT + 1,
            ),
        )
        assert resp.status_code == 422, resp.text
        assert await _count_transactions(session, budget.id) == 0

    async def test_income_amount_at_cap_accepted(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = _random_tid()
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        wallet, category = await seed_income_fixtures(session, budget)

        resp = await client.post(
            "/api/v1/transactions/income",
            headers=auth_headers(telegram_id),
            json=txn_payload(
                wallet_id=str(wallet.id),
                income_category_id=str(category.id),
                amount=MAX_AMOUNT,
            ),
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["amount"] == MAX_AMOUNT


class TestRateBounds:
    async def _make_currency_wallets(
        self, session: AsyncSession, budget_id: uuid.UUID
    ) -> tuple[Wallet, Wallet]:
        wallet_uzs = Wallet(family_budget_id=budget_id, name="UZS", currency="UZS")
        wallet_usd = Wallet(family_budget_id=budget_id, name="USD", currency="USD")
        session.add_all([wallet_uzs, wallet_usd])
        await session.flush()
        return wallet_uzs, wallet_usd

    async def test_rate_huge_scientific_notation_rejected(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = _random_tid()
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        wallet_uzs, wallet_usd = await self._make_currency_wallets(session, budget.id)

        resp = await client.post(
            "/api/v1/transactions/transfer",
            headers=auth_headers(telegram_id),
            json=txn_payload(
                wallet_id=str(wallet_uzs.id),
                to_wallet_id=str(wallet_usd.id),
                amount=1000,
                rate="1E+100",
            ),
        )
        assert resp.status_code == 422, resp.text
        assert await _count_transactions(session, budget.id) == 0

    async def test_rate_nan_rejected(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = _random_tid()
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        wallet_uzs, wallet_usd = await self._make_currency_wallets(session, budget.id)

        resp = await client.post(
            "/api/v1/transactions/transfer",
            headers=auth_headers(telegram_id),
            json=txn_payload(
                wallet_id=str(wallet_uzs.id),
                to_wallet_id=str(wallet_usd.id),
                amount=1000,
                rate="NaN",
            ),
        )
        assert resp.status_code == 422, resp.text
        assert await _count_transactions(session, budget.id) == 0

    async def test_rate_zero_rejected(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = _random_tid()
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        wallet_uzs, wallet_usd = await self._make_currency_wallets(session, budget.id)

        resp = await client.post(
            "/api/v1/transactions/transfer",
            headers=auth_headers(telegram_id),
            json=txn_payload(
                wallet_id=str(wallet_uzs.id),
                to_wallet_id=str(wallet_usd.id),
                amount=1000,
                rate="0",
            ),
        )
        assert resp.status_code == 422, resp.text
        assert await _count_transactions(session, budget.id) == 0


class TestComputedToAmountBound:
    async def test_exchange_computed_to_amount_overflow_rejected(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = _random_tid()
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id)
        wallet_usd = Wallet(family_budget_id=budget.id, name="USD", currency="USD")
        wallet_uzs = Wallet(family_budget_id=budget.id, name="UZS", currency="UZS")
        session.add_all([wallet_usd, wallet_uzs])
        await session.flush()

        # Both amount and rate are individually within bounds (<= MAX_AMOUNT),
        # but USD -> UZS multiplies them, which overflows the storable range.
        resp = await client.post(
            "/api/v1/transactions/transfer",
            headers=auth_headers(telegram_id),
            json=txn_payload(
                wallet_id=str(wallet_usd.id),
                to_wallet_id=str(wallet_uzs.id),
                amount=MAX_AMOUNT,
                rate=2,
            ),
        )
        assert resp.status_code == 422, resp.text
        assert await _count_transactions(session, budget.id) == 0


class TestGoalTargetAmountBound:
    async def test_goal_target_amount_over_cap_rejected(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        telegram_id = _random_tid()
        user, budget = await create_user_with_budget(session, telegram_id=telegram_id, role="owner")
        wallet = Wallet(
            family_budget_id=budget.id,
            name="Накопления",
            currency="UZS",
            is_personal=False,
        )
        session.add(wallet)
        await session.flush()

        resp = await client.post(
            "/api/v1/goals",
            headers=auth_headers(telegram_id),
            json={"wallet_id": str(wallet.id), "target_amount": MAX_AMOUNT + 1},
        )
        assert resp.status_code == 422, resp.text
