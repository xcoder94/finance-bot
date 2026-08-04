import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction


async def remap_transaction_categories_to_budget(
    session: AsyncSession,
    transactions: Sequence[Transaction],
    target_budget_id: uuid.UUID,
) -> None:
    if not transactions:
        return

    target_income = (
        await session.scalars(
            select(IncomeCategory).where(
                IncomeCategory.family_budget_id == target_budget_id,
                IncomeCategory.is_deleted.is_(False),
            )
        )
    ).all()
    income_by_key = {
        cat.translation_key: cat.id
        for cat in target_income
        if cat.translation_key is not None
    }

    target_expense = (
        await session.scalars(
            select(ExpenseCategory).where(
                ExpenseCategory.family_budget_id == target_budget_id,
                ExpenseCategory.is_deleted.is_(False),
            )
        )
    ).all()
    expense_by_key = {
        cat.translation_key: cat.id
        for cat in target_expense
        if cat.translation_key is not None
    }

    old_income_ids = {
        txn.income_category_id for txn in transactions if txn.income_category_id is not None
    }
    old_income_by_id: dict[uuid.UUID, IncomeCategory] = {}
    if old_income_ids:
        for cat in (
            await session.scalars(
                select(IncomeCategory).where(IncomeCategory.id.in_(old_income_ids))
            )
        ).all():
            old_income_by_id[cat.id] = cat

    old_expense_ids = {
        txn.expense_category_id for txn in transactions if txn.expense_category_id is not None
    }
    old_expense_by_id: dict[uuid.UUID, ExpenseCategory] = {}
    if old_expense_ids:
        for cat in (
            await session.scalars(
                select(ExpenseCategory).where(ExpenseCategory.id.in_(old_expense_ids))
            )
        ).all():
            old_expense_by_id[cat.id] = cat

    for txn in transactions:
        if txn.income_category_id is not None:
            old_cat = old_income_by_id.get(txn.income_category_id)
            key = old_cat.translation_key if old_cat is not None else None
            txn.income_category_id = income_by_key.get(key) if key is not None else None

        if txn.expense_category_id is not None:
            old_cat = old_expense_by_id.get(txn.expense_category_id)
            key = old_cat.translation_key if old_cat is not None else None
            txn.expense_category_id = expense_by_key.get(key) if key is not None else None
