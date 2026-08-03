import socket
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine
from app.models.family_budget import FamilyBudget
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.history_analytics import get_wallet_balances


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


async def create_user(
    session: AsyncSession,
    *,
    telegram_id: int,
) -> tuple[User, FamilyBudget]:
    budget = FamilyBudget(invite_token=f"test-{uuid.uuid4()}")
    session.add(budget)
    await session.flush()
    user = User(
        telegram_id=telegram_id,
        family_budget_id=budget.id,
        role="owner",
        language="ru",
    )
    session.add(user)
    await session.flush()
    return user, budget


pytestmark = [
    pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available"),
    pytest.mark.anyio,
]


class TestWalletBalancesSharedOnly:
    async def test_personal_wallet_income_excluded_from_balance(self) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_001_001_001)
            income_cat = IncomeCategory(family_budget_id=budget.id, name="Salary")
            shared_wallet = Wallet(
                family_budget_id=budget.id, name="Shared UZS", currency="UZS"
            )
            personal_wallet = Wallet(
                family_budget_id=budget.id,
                name="Personal UZS",
                currency="UZS",
                is_personal=True,
                owner_user_id=user.id,
            )
            session.add_all([income_cat, shared_wallet, personal_wallet])
            await session.flush()

            dt = datetime(2026, 8, 1, tzinfo=UTC)
            session.add_all(
                [
                    Transaction(
                        family_budget_id=budget.id,
                        type="income",
                        wallet_id=shared_wallet.id,
                        amount=10_000,
                        income_category_id=income_cat.id,
                        created_by_user_id=user.id,
                        transaction_date=dt,
                    ),
                    Transaction(
                        family_budget_id=budget.id,
                        type="income",
                        wallet_id=personal_wallet.id,
                        amount=50_000,
                        income_category_id=income_cat.id,
                        created_by_user_id=user.id,
                        transaction_date=dt,
                    ),
                ]
            )
            await session.flush()

            result = await get_wallet_balances(session, budget.id)
            by_currency = {row.currency: row.balance for row in result.balances}
            assert by_currency["UZS"] == 10_000

    async def test_transfer_to_personal_wallet_excluded(self) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_001_001_002)
            shared_a = Wallet(
                family_budget_id=budget.id, name="Shared A", currency="UZS"
            )
            shared_b = Wallet(
                family_budget_id=budget.id, name="Shared B", currency="UZS"
            )
            personal = Wallet(
                family_budget_id=budget.id,
                name="Personal",
                currency="UZS",
                is_personal=True,
                owner_user_id=user.id,
            )
            income_cat = IncomeCategory(family_budget_id=budget.id, name="Salary")
            session.add_all([shared_a, shared_b, personal, income_cat])
            await session.flush()

            dt = datetime(2026, 8, 2, tzinfo=UTC)
            session.add_all(
                [
                    Transaction(
                        family_budget_id=budget.id,
                        type="income",
                        wallet_id=shared_a.id,
                        amount=20_000,
                        income_category_id=income_cat.id,
                        created_by_user_id=user.id,
                        transaction_date=dt,
                    ),
                    Transaction(
                        family_budget_id=budget.id,
                        type="transfer",
                        wallet_id=shared_a.id,
                        to_wallet_id=personal.id,
                        amount=5_000,
                        to_amount=5_000,
                        created_by_user_id=user.id,
                        transaction_date=dt,
                    ),
                    Transaction(
                        family_budget_id=budget.id,
                        type="transfer",
                        wallet_id=shared_a.id,
                        to_wallet_id=shared_b.id,
                        amount=3_000,
                        to_amount=3_000,
                        created_by_user_id=user.id,
                        transaction_date=dt,
                    ),
                ]
            )
            await session.flush()

            result = await get_wallet_balances(session, budget.id)
            by_currency = {row.currency: row.balance for row in result.balances}
            # 20k income; -5k out to personal (dest excluded); shared transfer nets zero
            assert by_currency["UZS"] == 15_000
