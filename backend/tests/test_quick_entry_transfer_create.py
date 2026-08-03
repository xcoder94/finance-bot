import socket
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine
from app.models.family_budget import FamilyBudget
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.quick_entry_balance import wallet_balance
from app.services.quick_entry_transfer import (
    ResolvedTransferWallets,
    create_quick_entry_transfer,
    resolve_transfer_wallets,
)


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
    budget: FamilyBudget | None = None,
) -> tuple[User, FamilyBudget]:
    if budget is None:
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


def make_wallet(
    budget: FamilyBudget,
    *,
    name: str,
    currency: str = "UZS",
) -> Wallet:
    return Wallet(family_budget_id=budget.id, name=name, currency=currency)


async def seed_transfer_wallets(
    session: AsyncSession, budget: FamilyBudget
) -> tuple[Wallet, Wallet, Wallet, Wallet]:
    cash_uzs = make_wallet(budget, name="Наличный сум", currency="UZS")
    card_uzs = make_wallet(budget, name="Карта сум", currency="UZS")
    cash_usd = make_wallet(budget, name="Наличный USD", currency="USD")
    card_usd = make_wallet(budget, name="Карта USD", currency="USD")
    session.add_all([cash_uzs, card_uzs, cash_usd, card_usd])
    await session.flush()
    return cash_uzs, card_uzs, cash_usd, card_usd


async def seed_income(
    session: AsyncSession,
    user: User,
    budget: FamilyBudget,
    wallet: Wallet,
    amount: int,
) -> None:
    txn_date = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    session.add(
        Transaction(
            family_budget_id=budget.id,
            type="income",
            wallet_id=wallet.id,
            amount=amount,
            created_by_user_id=user.id,
            transaction_date=txn_date,
        )
    )
    await session.flush()


pytestmark = [
    pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available"),
    pytest.mark.anyio,
]


class TestResolveTransferWallets:
    async def test_resolves_two_uzs_wallets_by_hints(self) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=1_006_001_001)
            cash_uzs, card_uzs, _, _ = await seed_transfer_wallets(session, budget)

            resolved = await resolve_transfer_wallets(
                session,
                budget.id,
                user,
                from_hint="карта",
                to_hint="наличн",
                amount_currency="UZS",
                default_wallet=cash_uzs,
            )

            assert isinstance(resolved, ResolvedTransferWallets)
            assert resolved.from_wallet == card_uzs
            assert resolved.to_wallet == cash_uzs


class TestCreateQuickEntryTransfer:
    async def test_same_currency_transfer(self) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=1_006_002_001)
            cash_uzs, card_uzs, _, _ = await seed_transfer_wallets(session, budget)
            await seed_income(session, user, budget, card_uzs, 500_000)
            txn_date = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)

            assert await wallet_balance(session, card_uzs.id) == 500_000
            assert await wallet_balance(session, cash_uzs.id) == 0

            txn = await create_quick_entry_transfer(
                session,
                user,
                from_wallet_id=card_uzs.id,
                to_wallet_id=cash_uzs.id,
                amount=200_000,
                rate=None,
                comment="переложил",
                transaction_date=txn_date,
            )

            assert txn.type == "transfer"
            assert txn.amount == 200_000
            assert txn.to_amount == 200_000
            assert txn.rate is None
            assert await wallet_balance(session, card_uzs.id) == 300_000
            assert await wallet_balance(session, cash_uzs.id) == 200_000

    async def test_usd_to_uzs_exchange_with_rate(self) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=1_006_003_001)
            _, card_uzs, _, card_usd = await seed_transfer_wallets(session, budget)
            await seed_income(session, user, budget, card_usd, 500)
            txn_date = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)

            txn = await create_quick_entry_transfer(
                session,
                user,
                from_wallet_id=card_usd.id,
                to_wallet_id=card_uzs.id,
                amount=100,
                rate=Decimal(12_800),
                comment=None,
                transaction_date=txn_date,
            )

            assert txn.type == "transfer"
            assert txn.amount == 100
            assert txn.to_amount == 1_280_000
            assert txn.rate == Decimal(12_800)
            assert await wallet_balance(session, card_usd.id) == 400
            assert await wallet_balance(session, card_uzs.id) == 1_280_000
