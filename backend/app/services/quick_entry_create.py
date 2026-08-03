from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.services.quick_entry_categories import strip_parent_category
from app.services.transactions import (
    validate_quick_entry_expense_refs,
    validate_quick_entry_income_refs,
)

EVENTS_PARENT_NAME = "События и тои"
PODARKI_NAME = "Подарки"


async def create_quick_entry_expense(
    session: AsyncSession,
    user: User,
    *,
    amount: int,
    wallet_id: uuid.UUID,
    expense_category_id: uuid.UUID | None,
    comment: str | None,
    transaction_date: datetime,
) -> Transaction:
    await validate_quick_entry_expense_refs(
        session,
        user.family_budget_id,
        wallet_id,
        expense_category_id,
    )
    transaction = Transaction(
        family_budget_id=user.family_budget_id,
        type="expense",
        wallet_id=wallet_id,
        amount=amount,
        expense_category_id=expense_category_id,
        comment=comment,
        created_by_user_id=user.id,
        transaction_date=transaction_date,
    )
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    return transaction


async def create_quick_entry_income(
    session: AsyncSession,
    user: User,
    *,
    amount: int,
    wallet_id: uuid.UUID,
    income_category_id: uuid.UUID | None,
    comment: str | None,
    transaction_date: datetime,
) -> Transaction:
    await validate_quick_entry_income_refs(
        session,
        user.family_budget_id,
        wallet_id,
        income_category_id,
    )
    transaction = Transaction(
        family_budget_id=user.family_budget_id,
        type="income",
        wallet_id=wallet_id,
        amount=amount,
        income_category_id=income_category_id,
        comment=comment,
        created_by_user_id=user.id,
        transaction_date=transaction_date,
    )
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    return transaction


async def _find_expense_sub_by_name(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    name: str,
) -> uuid.UUID | None:
    stmt = select(ExpenseCategory).where(
        ExpenseCategory.family_budget_id == family_budget_id,
        ExpenseCategory.is_deleted.is_(False),
        ExpenseCategory.parent_id.is_not(None),
        ExpenseCategory.name == name,
    )
    category = await session.scalar(stmt)
    return category.id if category is not None else None


async def _find_expense_parent_by_name(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    name: str,
) -> uuid.UUID | None:
    stmt = select(ExpenseCategory).where(
        ExpenseCategory.family_budget_id == family_budget_id,
        ExpenseCategory.is_deleted.is_(False),
        ExpenseCategory.parent_id.is_(None),
        ExpenseCategory.name == name,
    )
    category = await session.scalar(stmt)
    return category.id if category is not None else None


async def _find_income_by_name(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    name: str,
) -> uuid.UUID | None:
    stmt = select(IncomeCategory).where(
        IncomeCategory.family_budget_id == family_budget_id,
        IncomeCategory.is_deleted.is_(False),
        IncomeCategory.name == name,
    )
    category = await session.scalar(stmt)
    return category.id if category is not None else None


async def _find_expense_sub_under_parent(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    sub_name: str,
    parent_name: str,
) -> uuid.UUID | None:
    parent_stmt = select(ExpenseCategory).where(
        ExpenseCategory.family_budget_id == family_budget_id,
        ExpenseCategory.is_deleted.is_(False),
        ExpenseCategory.parent_id.is_(None),
        ExpenseCategory.name == parent_name,
    )
    parent = await session.scalar(parent_stmt)
    if parent is None:
        return None
    sub_stmt = select(ExpenseCategory).where(
        ExpenseCategory.family_budget_id == family_budget_id,
        ExpenseCategory.is_deleted.is_(False),
        ExpenseCategory.parent_id == parent.id,
        ExpenseCategory.name == sub_name,
    )
    sub = await session.scalar(sub_stmt)
    return sub.id if sub is not None else None


async def resolve_category_id(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    *,
    op_type: Literal["expense", "income"],
    category_name: str | None,
    button_choice: Literal["expense", "income"] | None = None,
) -> uuid.UUID | None:
    if category_name is None or not category_name.strip():
        return None

    name = strip_parent_category(category_name.strip())
    if name is None or not name:
        return None

    if name == PODARKI_NAME and button_choice is not None:
        if button_choice == "income":
            return await _find_income_by_name(session, family_budget_id, PODARKI_NAME)
        return await _find_expense_sub_under_parent(
            session,
            family_budget_id,
            PODARKI_NAME,
            EVENTS_PARENT_NAME,
        )

    sub_id = await _find_expense_sub_by_name(session, family_budget_id, name)
    if sub_id is not None:
        return sub_id

    parent_id = await _find_expense_parent_by_name(session, family_budget_id, name)
    if parent_id is not None:
        return parent_id

    if op_type == "income":
        return await _find_income_by_name(session, family_budget_id, name)

    return None
