import socket
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.income_category import IncomeCategory
from app.models.user import User
from app.models.wallet import Wallet
from app.services.quick_entry_create import (
    create_quick_entry_expense,
    create_quick_entry_income,
    resolve_category_id,
)
from app.services.transactions import validate_expense_refs


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


async def seed_expense_tree(
    session: AsyncSession, budget: FamilyBudget
) -> tuple[Wallet, ExpenseCategory, ExpenseCategory, ExpenseCategory, ExpenseCategory]:
    wallet = Wallet(family_budget_id=budget.id, name="Карта сум", currency="UZS")
    food = ExpenseCategory(family_budget_id=budget.id, name="Еда")
    events = ExpenseCategory(family_budget_id=budget.id, name="События и тои")
    session.add_all([wallet, food, events])
    await session.flush()
    groceries = ExpenseCategory(
        family_budget_id=budget.id, name="Продукты", parent_id=food.id
    )
    gifts = ExpenseCategory(
        family_budget_id=budget.id, name="Подарки", parent_id=events.id
    )
    session.add_all([groceries, gifts])
    await session.flush()
    return wallet, food, groceries, events, gifts


async def seed_income_categories(
    session: AsyncSession, budget: FamilyBudget
) -> IncomeCategory:
    gifts = IncomeCategory(family_budget_id=budget.id, name="Подарки")
    salary = IncomeCategory(family_budget_id=budget.id, name="Зарплата")
    session.add_all([gifts, salary])
    await session.flush()
    return gifts


pytestmark = [
    pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available"),
    pytest.mark.anyio,
]


class TestCreateQuickEntryExpense:
    async def test_parent_category_allowed(self) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=1_001_001)
            wallet, food, _, _, _ = await seed_expense_tree(session, budget)
            txn_date = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)

            txn = await create_quick_entry_expense(
                session,
                user,
                amount=50_000,
                wallet_id=wallet.id,
                expense_category_id=food.id,
                comment="обед",
                transaction_date=txn_date,
            )

            assert txn.type == "expense"
            assert txn.expense_category_id == food.id
            assert txn.amount == 50_000
            assert txn.comment == "обед"

    async def test_null_category_for_bez_kategorii(self) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=1_001_002)
            wallet, _, _, _, _ = await seed_expense_tree(session, budget)
            txn_date = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)

            txn = await create_quick_entry_expense(
                session,
                user,
                amount=300_000,
                wallet_id=wallet.id,
                expense_category_id=None,
                comment="Азиз",
                transaction_date=txn_date,
            )

            assert txn.type == "expense"
            assert txn.expense_category_id is None
            assert txn.comment == "Азиз"

    async def test_subcategory_still_works(self) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=1_001_003)
            wallet, _, groceries, _, _ = await seed_expense_tree(session, budget)

            txn = await create_quick_entry_expense(
                session,
                user,
                amount=200_000,
                wallet_id=wallet.id,
                expense_category_id=groceries.id,
                comment=None,
                transaction_date=datetime(2026, 8, 3, 12, 0, tzinfo=UTC),
            )

            assert txn.expense_category_id == groceries.id


class TestCreateQuickEntryIncome:
    async def test_with_and_without_category(self) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=1_001_004)
            wallet, _, _, _, _ = await seed_expense_tree(session, budget)
            income_gifts = await seed_income_categories(session, budget)
            txn_date = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)

            with_cat = await create_quick_entry_income(
                session,
                user,
                amount=500_000,
                wallet_id=wallet.id,
                income_category_id=income_gifts.id,
                comment=None,
                transaction_date=txn_date,
            )
            assert with_cat.type == "income"
            assert with_cat.income_category_id == income_gifts.id

            without_cat = await create_quick_entry_income(
                session,
                user,
                amount=100_000,
                wallet_id=wallet.id,
                income_category_id=None,
                comment=None,
                transaction_date=txn_date,
            )
            assert without_cat.income_category_id is None


class TestApiValidateExpenseRefs:
    async def test_api_accepts_parent_category(self) -> None:
        async with rollback_session() as session:
            _, budget = await create_user(session, telegram_id=1_001_005)
            wallet, food, _, _, _ = await seed_expense_tree(session, budget)

            await validate_expense_refs(session, budget.id, wallet.id, food.id)


class TestResolveCategoryId:
    async def test_empty_name_returns_none(self) -> None:
        async with rollback_session() as session:
            _, budget = await create_user(session, telegram_id=1_001_006)

            assert (
                await resolve_category_id(
                    session, budget.id, op_type="expense", category_name=None
                )
                is None
            )
            assert (
                await resolve_category_id(
                    session, budget.id, op_type="expense", category_name="  "
                )
                is None
            )

    async def test_matches_subcategory_then_parent(self) -> None:
        async with rollback_session() as session:
            _, budget = await create_user(session, telegram_id=1_001_007)
            _, food, groceries, _, _ = await seed_expense_tree(session, budget)

            assert (
                await resolve_category_id(
                    session, budget.id, op_type="expense", category_name="Продукты"
                )
                == groceries.id
            )
            assert (
                await resolve_category_id(
                    session, budget.id, op_type="expense", category_name="Еда"
                )
                == food.id
            )

    async def test_strips_parent_prefix_from_model_output(self) -> None:
        async with rollback_session() as session:
            _, budget = await create_user(session, telegram_id=1_001_008)
            _, _, groceries, _, _ = await seed_expense_tree(session, budget)

            resolved = await resolve_category_id(
                session,
                budget.id,
                op_type="expense",
                category_name="Еда: Продукты",
            )
            assert resolved == groceries.id

    async def test_income_name_for_income_op(self) -> None:
        async with rollback_session() as session:
            _, budget = await create_user(session, telegram_id=1_001_009)
            await seed_expense_tree(session, budget)
            await seed_income_categories(session, budget)

            resolved = await resolve_category_id(
                session, budget.id, op_type="income", category_name="Зарплата"
            )
            assert resolved is not None

    async def test_podarki_collision_resolved_by_button_choice(self) -> None:
        async with rollback_session() as session:
            _, budget = await create_user(session, telegram_id=1_001_010)
            _, _, _, _, expense_gifts = await seed_expense_tree(session, budget)
            income_gifts = await seed_income_categories(session, budget)

            expense_id = await resolve_category_id(
                session,
                budget.id,
                op_type="expense",
                category_name="Подарки",
                button_choice="expense",
            )
            income_id = await resolve_category_id(
                session,
                budget.id,
                op_type="income",
                category_name="Подарки",
                button_choice="income",
            )

            assert expense_id == expense_gifts.id
            assert income_id == income_gifts.id
            assert expense_id != income_id
