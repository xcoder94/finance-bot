import socket
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine
from app.models.family_budget import FamilyBudget
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.quick_entry_balance import wallet_balance
from app.services.quick_entry_wallets import (
    CurrencyMissing,
    list_wallets_for_parse,
    resolve_wallet,
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
    role: str = "owner",
    budget: FamilyBudget | None = None,
) -> tuple[User, FamilyBudget]:
    if budget is None:
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


def make_wallet(
    budget: FamilyBudget,
    *,
    name: str,
    currency: str = "UZS",
    is_personal: bool = False,
    owner_user_id: uuid.UUID | None = None,
) -> Wallet:
    return Wallet(
        family_budget_id=budget.id,
        name=name,
        currency=currency,
        is_personal=is_personal,
        owner_user_id=owner_user_id,
    )


pytestmark = [
    pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available"),
    pytest.mark.anyio,
]


class TestListWalletsForParse:
    async def test_includes_shared_and_writer_personal_only(self) -> None:
        async with rollback_session() as session:
            owner, budget = await create_user(session, telegram_id=1_001_001_001)
            member, _ = await create_user(
                session, telegram_id=1_001_001_002, role="member", budget=budget
            )
            shared = make_wallet(budget, name="Карта сум")
            owner_personal = make_wallet(
                budget,
                name="Owner stash",
                is_personal=True,
                owner_user_id=owner.id,
            )
            member_personal = make_wallet(
                budget,
                name="Member stash",
                is_personal=True,
                owner_user_id=member.id,
            )
            session.add_all([shared, owner_personal, member_personal])
            await session.flush()

            owner_wallets = await list_wallets_for_parse(session, budget.id, owner)
            owner_names = {w.name for w in owner_wallets}
            assert "Карта сум" in owner_names
            assert "Owner stash" in owner_names
            assert "Member stash" not in owner_names

            member_wallets = await list_wallets_for_parse(session, budget.id, member)
            member_names = {w.name for w in member_wallets}
            assert "Карта сум" in member_names
            assert "Member stash" in member_names
            assert "Owner stash" not in member_names

    async def test_acceptance_14_member_b_never_sees_member_a_personal_names(
        self,
    ) -> None:
        async with rollback_session() as session:
            member_a, budget = await create_user(session, telegram_id=1_002_001_001)
            member_b, _ = await create_user(
                session, telegram_id=1_002_001_002, role="member", budget=budget
            )
            secret_name = f"A-personal-{uuid.uuid4().hex[:8]}"
            session.add_all(
                [
                    make_wallet(budget, name="Shared wallet"),
                    make_wallet(
                        budget,
                        name=secret_name,
                        is_personal=True,
                        owner_user_id=member_a.id,
                    ),
                ]
            )
            await session.flush()

            names = {w.name for w in await list_wallets_for_parse(session, budget.id, member_b)}
            assert secret_name not in names

    async def test_limits_shared_wallets_to_ten(self) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=1_003_001_001)
            for i in range(12):
                session.add(make_wallet(budget, name=f"Shared-{i:02d}"))
            session.add(
                make_wallet(
                    budget,
                    name="My personal",
                    is_personal=True,
                    owner_user_id=user.id,
                )
            )
            await session.flush()

            wallets = await list_wallets_for_parse(session, budget.id, user)
            shared = [w for w in wallets if not w.is_personal]
            personal = [w for w in wallets if w.is_personal]
            assert len(shared) == 10
            assert len(personal) == 1
            assert shared[0].name == "Shared-00"


class TestResolveWallet:
    async def test_hint_match_case_insensitive(self) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=1_004_001_001)
            default = make_wallet(budget, name="Наличный сум")
            card = make_wallet(budget, name="Карта сум")
            session.add_all([default, card])
            await session.flush()

            resolved = await resolve_wallet(
                session=session,
                family_budget_id=budget.id,
                writer=user,
                wallet_hint="карта",
                currency=None,
                default_wallet=default,
            )
            assert resolved == card

    async def test_hint_miss_uses_default(self) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=1_004_002_001)
            default = make_wallet(budget, name="Карта сум")
            session.add(default)
            await session.flush()

            resolved = await resolve_wallet(
                session=session,
                family_budget_id=budget.id,
                writer=user,
                wallet_hint="несуществующий",
                currency=None,
                default_wallet=default,
            )
            assert resolved == default

    async def test_currency_switch_when_mismatch(self) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=1_004_003_001)
            default = make_wallet(budget, name="Карта сум", currency="UZS")
            usd_wallet = make_wallet(budget, name="Карта USD", currency="USD")
            session.add_all([default, usd_wallet])
            await session.flush()

            resolved = await resolve_wallet(
                session=session,
                family_budget_id=budget.id,
                writer=user,
                wallet_hint=None,
                currency="USD",
                default_wallet=default,
            )
            assert resolved == usd_wallet

    async def test_currency_missing_when_no_wallet_in_currency(self) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=1_004_004_001)
            default = make_wallet(budget, name="Карта сум", currency="UZS")
            session.add(default)
            await session.flush()

            resolved = await resolve_wallet(
                session=session,
                family_budget_id=budget.id,
                writer=user,
                wallet_hint=None,
                currency="USD",
                default_wallet=default,
            )
            assert isinstance(resolved, CurrencyMissing)
            assert resolved.currency == "USD"


class TestWalletBalance:
    async def test_sums_income_expense_and_transfers(self) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=1_005_001_001)
            wallet_a = make_wallet(budget, name="A", currency="UZS")
            wallet_b = make_wallet(budget, name="B", currency="UZS")
            session.add_all([wallet_a, wallet_b])
            await session.flush()
            txn_date = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
            session.add_all(
                [
                    Transaction(
                        family_budget_id=budget.id,
                        type="income",
                        wallet_id=wallet_a.id,
                        amount=1000,
                        created_by_user_id=user.id,
                        transaction_date=txn_date,
                    ),
                    Transaction(
                        family_budget_id=budget.id,
                        type="expense",
                        wallet_id=wallet_a.id,
                        amount=200,
                        created_by_user_id=user.id,
                        transaction_date=txn_date,
                    ),
                    Transaction(
                        family_budget_id=budget.id,
                        type="transfer",
                        wallet_id=wallet_a.id,
                        to_wallet_id=wallet_b.id,
                        amount=300,
                        to_amount=300,
                        created_by_user_id=user.id,
                        transaction_date=txn_date,
                    ),
                    Transaction(
                        family_budget_id=budget.id,
                        type="transfer",
                        wallet_id=wallet_b.id,
                        to_wallet_id=wallet_a.id,
                        amount=50,
                        to_amount=50,
                        created_by_user_id=user.id,
                        transaction_date=txn_date,
                    ),
                ]
            )
            await session.flush()

            assert await wallet_balance(session, wallet_a.id) == 550

    async def test_ignores_soft_deleted_transactions(self) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=1_005_002_001)
            wallet = make_wallet(budget, name="A", currency="UZS")
            session.add(wallet)
            await session.flush()
            txn_date = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
            session.add(
                Transaction(
                    family_budget_id=budget.id,
                    type="income",
                    wallet_id=wallet.id,
                    amount=500,
                    created_by_user_id=user.id,
                    transaction_date=txn_date,
                    is_deleted=True,
                )
            )
            await session.flush()

            assert await wallet_balance(session, wallet.id) == 0
