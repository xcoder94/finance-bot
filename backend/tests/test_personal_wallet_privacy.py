"""Personal wallet privacy / data-integrity regression tests.

Covers two defects:

1. Category listing counts (income/expense) leaked other members' personal-
   wallet operations to the budget owner, contradicting docs/PRD.md:96-97
   ("A personal wallet is invisible to everyone except its holder, including
   the budget owner").
2. A transfer into or out of a departing member's personal wallet was
   orphaned on departure: the wallet moved to the member's new budget but
   the transaction row stayed behind, per docs/PRD.md:892-895 ("Personal
   wallets always follow the person, together with their operations").

DB-backed tests use a real PostgreSQL instance and skip cleanly when one is
not reachable (same pattern as tests/test_cascade_fallback_log.py). Unit
tests exercise the query-construction / selection logic directly and always
run, so the fix has coverage even without a database.
"""

from __future__ import annotations

import socket
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.categories import _count_visible_category_transactions
from app.db import engine
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.membership_lifecycle import (
    detach_member_to_own_budget,
    personal_wallet_transaction_clause,
)
from app.services.quick_entry_balance import wallet_balance


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


async def make_budget(session: AsyncSession) -> FamilyBudget:
    budget = FamilyBudget(invite_token=f"test-{uuid.uuid4()}")
    session.add(budget)
    await session.flush()
    return budget


async def make_user(
    session: AsyncSession, budget: FamilyBudget, *, telegram_id: int, role: str
) -> User:
    user = User(
        telegram_id=telegram_id,
        family_budget_id=budget.id,
        role=role,
        language="ru",
    )
    session.add(user)
    await session.flush()
    return user


def make_wallet(
    budget: FamilyBudget,
    *,
    name: str,
    is_personal: bool = False,
    owner_user_id: uuid.UUID | None = None,
    currency: str = "UZS",
) -> Wallet:
    return Wallet(
        family_budget_id=budget.id,
        name=name,
        currency=currency,
        is_personal=is_personal,
        owner_user_id=owner_user_id,
    )


# ---------------------------------------------------------------------------
# Bug 1 — category transaction counts must not leak other members' personal
# operations. DB-backed.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _db_available(), reason="PostgreSQL is not reachable on 127.0.0.1:5432"
)
@pytest.mark.anyio
async def test_expense_category_count_hides_other_members_personal_ops() -> None:
    async with rollback_session() as session:
        budget = await make_budget(session)
        owner = await make_user(session, budget, telegram_id=1001, role="owner")
        member = await make_user(session, budget, telegram_id=1002, role="member")

        personal_wallet = make_wallet(
            budget, name="Личный member", is_personal=True, owner_user_id=member.id
        )
        session.add(personal_wallet)
        await session.flush()

        category = ExpenseCategory(family_budget_id=budget.id, name="Еда")
        session.add(category)
        await session.flush()

        txn = Transaction(
            family_budget_id=budget.id,
            type="expense",
            wallet_id=personal_wallet.id,
            amount=1000,
            expense_category_id=category.id,
            created_by_user_id=member.id,
            transaction_date=__import__("datetime").datetime.now(
                __import__("datetime").UTC
            ),
        )
        session.add(txn)
        await session.flush()

        owner_count = await _count_visible_category_transactions(
            session,
            category_column=Transaction.expense_category_id,
            category_id=category.id,
            user=owner,
        )
        member_count = await _count_visible_category_transactions(
            session,
            category_column=Transaction.expense_category_id,
            category_id=category.id,
            user=member,
        )

        assert owner_count == 0
        assert member_count == 1


@pytest.mark.skipif(
    not _db_available(), reason="PostgreSQL is not reachable on 127.0.0.1:5432"
)
@pytest.mark.anyio
async def test_income_category_count_hides_other_members_personal_ops() -> None:
    async with rollback_session() as session:
        budget = await make_budget(session)
        owner = await make_user(session, budget, telegram_id=2001, role="owner")
        member = await make_user(session, budget, telegram_id=2002, role="member")

        personal_wallet = make_wallet(
            budget, name="Личный member", is_personal=True, owner_user_id=member.id
        )
        session.add(personal_wallet)
        await session.flush()

        category = IncomeCategory(family_budget_id=budget.id, name="Подработка")
        session.add(category)
        await session.flush()

        import datetime

        txn = Transaction(
            family_budget_id=budget.id,
            type="income",
            wallet_id=personal_wallet.id,
            amount=5000,
            income_category_id=category.id,
            created_by_user_id=member.id,
            transaction_date=datetime.datetime.now(datetime.UTC),
        )
        session.add(txn)
        await session.flush()

        owner_count = await _count_visible_category_transactions(
            session,
            category_column=Transaction.income_category_id,
            category_id=category.id,
            user=owner,
        )
        member_count = await _count_visible_category_transactions(
            session,
            category_column=Transaction.income_category_id,
            category_id=category.id,
            user=member,
        )

        assert owner_count == 0
        assert member_count == 1


# ---------------------------------------------------------------------------
# Bug 1 — unit-level coverage that always runs: exercises the actual SQL the
# fix builds (join + visible_wallets_clause), without needing a database.
# ---------------------------------------------------------------------------


class _FakeScalarResult:
    def __init__(self, value: int) -> None:
        self._value = value

    async def __call__(self, *_args, **_kwargs):
        return self._value


@pytest.mark.anyio
async def test_count_visible_category_transactions_query_shape() -> None:
    """The generated statement must join Wallet and apply
    visible_wallets_clause(user) — i.e. it must not be a bare family-scoped
    count. This is a compile-time check of the query construction, so it
    runs without a database."""
    captured: dict[str, object] = {}

    class FakeSession:
        async def scalar(self, stmt):
            captured["stmt"] = stmt
            return 0

    fake_user = User(
        id=uuid.uuid4(),
        telegram_id=1,
        family_budget_id=uuid.uuid4(),
        role="owner",
        language="ru",
    )
    fake_user.id = uuid.uuid4()

    category_id = uuid.uuid4()
    await _count_visible_category_transactions(
        FakeSession(),
        category_column=Transaction.expense_category_id,
        category_id=category_id,
        user=fake_user,
    )

    compiled = str(captured["stmt"])
    assert "JOIN wallets" in compiled
    assert "wallets.is_personal" in compiled
    assert "wallets.owner_user_id" in compiled


# ---------------------------------------------------------------------------
# Bug 2 — a transfer into/out of a departing member's personal wallet must
# move with the wallet, not stay behind. DB-backed.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _db_available(), reason="PostgreSQL is not reachable on 127.0.0.1:5432"
)
@pytest.mark.anyio
async def test_transfer_into_personal_wallet_moves_with_departing_member() -> None:
    async with rollback_session() as session:
        old_budget = await make_budget(session)
        owner = await make_user(session, old_budget, telegram_id=3001, role="owner")
        member = await make_user(session, old_budget, telegram_id=3002, role="member")

        shared_wallet = make_wallet(old_budget, name="Общий кошелёк")
        personal_wallet = make_wallet(
            old_budget, name="Личный member", is_personal=True, owner_user_id=member.id
        )
        session.add_all([shared_wallet, personal_wallet])
        await session.flush()
        member.default_wallet_id = personal_wallet.id

        import datetime

        txn = Transaction(
            family_budget_id=old_budget.id,
            type="transfer",
            wallet_id=shared_wallet.id,
            to_wallet_id=personal_wallet.id,
            amount=10000,
            to_amount=10000,
            created_by_user_id=owner.id,
            transaction_date=datetime.datetime.now(datetime.UTC),
        )
        session.add(txn)
        await session.flush()

        new_budget = await detach_member_to_own_budget(
            session,
            departing_user=member,
            old_budget=old_budget,
            reason="left",
            bot=AsyncMock(),
        )
        await session.flush()

        await session.refresh(txn)
        assert txn.family_budget_id == new_budget.id, (
            "transfer must move with the personal wallet on its to_wallet_id side"
        )

        balance = await wallet_balance(session, personal_wallet.id)
        assert balance == 10000

        visible_in_new_budget = (
            await session.scalars(
                select(Transaction).where(
                    Transaction.family_budget_id == new_budget.id,
                    Transaction.id == txn.id,
                )
            )
        ).first()
        assert visible_in_new_budget is not None, (
            "balance and history visibility must agree: the departing member "
            "must see this transfer in their new budget's history"
        )


@pytest.mark.skipif(
    not _db_available(), reason="PostgreSQL is not reachable on 127.0.0.1:5432"
)
@pytest.mark.anyio
async def test_transfer_out_of_personal_wallet_moves_with_departing_member() -> None:
    async with rollback_session() as session:
        old_budget = await make_budget(session)
        owner = await make_user(session, old_budget, telegram_id=4001, role="owner")
        member = await make_user(session, old_budget, telegram_id=4002, role="member")

        shared_wallet = make_wallet(old_budget, name="Общий кошелёк")
        personal_wallet = make_wallet(
            old_budget, name="Личный member", is_personal=True, owner_user_id=member.id
        )
        session.add_all([shared_wallet, personal_wallet])
        await session.flush()
        member.default_wallet_id = personal_wallet.id

        import datetime

        txn = Transaction(
            family_budget_id=old_budget.id,
            type="transfer",
            wallet_id=personal_wallet.id,
            to_wallet_id=shared_wallet.id,
            amount=3000,
            to_amount=3000,
            created_by_user_id=member.id,
            transaction_date=datetime.datetime.now(datetime.UTC),
        )
        session.add(txn)
        await session.flush()

        new_budget = await detach_member_to_own_budget(
            session,
            departing_user=member,
            old_budget=old_budget,
            reason="left",
            bot=AsyncMock(),
        )
        await session.flush()

        await session.refresh(txn)
        assert txn.family_budget_id == new_budget.id, (
            "transfer must move with the personal wallet on its wallet_id side"
        )

        balance = await wallet_balance(session, personal_wallet.id)
        assert balance == -3000

        visible_in_new_budget = (
            await session.scalars(
                select(Transaction).where(
                    Transaction.family_budget_id == new_budget.id,
                    Transaction.id == txn.id,
                )
            )
        ).first()
        assert visible_in_new_budget is not None


# ---------------------------------------------------------------------------
# Bug 2 — unit-level coverage that always runs: exercises the selection
# clause directly, without needing a database.
# ---------------------------------------------------------------------------


def test_personal_wallet_transaction_clause_matches_either_side() -> None:
    personal_id = uuid.uuid4()

    clause = personal_wallet_transaction_clause([personal_id])
    compiled = str(clause)

    # Must reference both wallet_id and to_wallet_id so a transfer with the
    # personal wallet on EITHER side is picked up, combined with OR (not AND
    # — a transaction only has one of the two columns matching in practice).
    assert "wallet_id" in compiled
    assert "to_wallet_id" in compiled
    assert " OR " in compiled
