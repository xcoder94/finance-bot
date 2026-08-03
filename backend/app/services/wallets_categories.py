import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.wallet import Wallet


async def count_wallet_transactions(session: AsyncSession, wallet_id: uuid.UUID) -> int:
    stmt = select(func.count()).select_from(Transaction).where(
        Transaction.is_deleted.is_(False),
        or_(Transaction.wallet_id == wallet_id, Transaction.to_wallet_id == wallet_id),
    )
    return int(await session.scalar(stmt) or 0)


async def count_income_category_transactions(
    session: AsyncSession, category_id: uuid.UUID
) -> int:
    stmt = select(func.count()).select_from(Transaction).where(
        Transaction.is_deleted.is_(False),
        Transaction.income_category_id == category_id,
    )
    return int(await session.scalar(stmt) or 0)


async def count_expense_category_transactions(
    session: AsyncSession, category_id: uuid.UUID
) -> int:
    stmt = select(func.count()).select_from(Transaction).where(
        Transaction.is_deleted.is_(False),
        Transaction.expense_category_id == category_id,
    )
    return int(await session.scalar(stmt) or 0)


async def get_active_wallet(
    session: AsyncSession,
    wallet_id: uuid.UUID,
    family_budget_id: uuid.UUID,
) -> Wallet | None:
    stmt = select(Wallet).where(
        Wallet.id == wallet_id,
        Wallet.family_budget_id == family_budget_id,
        Wallet.is_deleted.is_(False),
    )
    return await session.scalar(stmt)


async def get_active_income_category(
    session: AsyncSession,
    category_id: uuid.UUID,
    family_budget_id: uuid.UUID,
) -> IncomeCategory | None:
    stmt = select(IncomeCategory).where(
        IncomeCategory.id == category_id,
        IncomeCategory.family_budget_id == family_budget_id,
        IncomeCategory.is_deleted.is_(False),
    )
    return await session.scalar(stmt)


async def get_active_expense_category(
    session: AsyncSession,
    category_id: uuid.UUID,
    family_budget_id: uuid.UUID,
) -> ExpenseCategory | None:
    stmt = select(ExpenseCategory).where(
        ExpenseCategory.id == category_id,
        ExpenseCategory.family_budget_id == family_budget_id,
        ExpenseCategory.is_deleted.is_(False),
    )
    return await session.scalar(stmt)


async def get_active_expense_parent(
    session: AsyncSession,
    parent_id: uuid.UUID,
    family_budget_id: uuid.UUID,
) -> ExpenseCategory | None:
    stmt = select(ExpenseCategory).where(
        ExpenseCategory.id == parent_id,
        ExpenseCategory.family_budget_id == family_budget_id,
        ExpenseCategory.is_deleted.is_(False),
    )
    return await session.scalar(stmt)


async def get_expense_parent_including_deleted(
    session: AsyncSession,
    parent_id: uuid.UUID,
    family_budget_id: uuid.UUID,
) -> ExpenseCategory | None:
    stmt = select(ExpenseCategory).where(
        ExpenseCategory.id == parent_id,
        ExpenseCategory.family_budget_id == family_budget_id,
    )
    return await session.scalar(stmt)


def soft_delete(record: Wallet | IncomeCategory | ExpenseCategory) -> None:
    record.is_deleted = True
    record.deleted_at = datetime.now(UTC)
