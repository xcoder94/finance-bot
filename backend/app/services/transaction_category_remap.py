import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.services.category_colors import assign_category_color


def _fold(name: str) -> str:
    return name.strip().casefold()


async def _resolve_income(
    session: AsyncSession,
    old: IncomeCategory,
    target_budget_id: uuid.UUID,
    cache: dict[uuid.UUID, uuid.UUID],
    adopt: bool = False,
) -> uuid.UUID:
    if old.id in cache:
        return cache[old.id]
    if old.family_budget_id == target_budget_id:
        cache[old.id] = old.id
        return old.id
    live = (
        await session.scalars(
            select(IncomeCategory).where(
                IncomeCategory.family_budget_id == target_budget_id,
                IncomeCategory.is_deleted.is_(False),
            )
        )
    ).all()
    if old.translation_key is not None:
        match = next((c for c in live if c.translation_key == old.translation_key), None)
    else:
        match = next(
            (c for c in live if c.translation_key is None and _fold(c.name) == _fold(old.name)),
            None,
        )
    if match is None:
        match = IncomeCategory(
            family_budget_id=target_budget_id,
            name=old.name,
            translation_key=old.translation_key,
            color_index=await assign_category_color(session, target_budget_id, kind="income"),
        )
        session.add(match)
        await session.flush()
    elif adopt:
        match.name = old.name
        match.color_index = old.color_index
    cache[old.id] = match.id
    return match.id


async def _resolve_expense(
    session: AsyncSession,
    old: ExpenseCategory,
    target_budget_id: uuid.UUID,
    cache: dict[uuid.UUID, uuid.UUID],
    adopt: bool = False,
) -> uuid.UUID:
    if old.id in cache:
        return cache[old.id]
    if old.family_budget_id == target_budget_id:
        cache[old.id] = old.id
        return old.id

    target_parent_id: uuid.UUID | None = None
    if old.parent_id is not None:
        old_parent = await session.get(ExpenseCategory, old.parent_id)
        if old_parent is not None:
            target_parent_id = await _resolve_expense(
                session, old_parent, target_budget_id, cache, adopt
            )

    live = (
        await session.scalars(
            select(ExpenseCategory).where(
                ExpenseCategory.family_budget_id == target_budget_id,
                ExpenseCategory.is_deleted.is_(False),
                ExpenseCategory.parent_id.is_(None)
                if target_parent_id is None
                else ExpenseCategory.parent_id == target_parent_id,
            )
        )
    ).all()
    if old.translation_key is not None:
        match = next((c for c in live if c.translation_key == old.translation_key), None)
    else:
        match = next(
            (c for c in live if c.translation_key is None and _fold(c.name) == _fold(old.name)),
            None,
        )
    if match is None:
        match = ExpenseCategory(
            family_budget_id=target_budget_id,
            name=old.name,
            translation_key=old.translation_key,
            parent_id=target_parent_id,
            is_protected=old.is_protected,
            color_index=await assign_category_color(
                session, target_budget_id, kind="expense", parent_id=target_parent_id
            ),
        )
        session.add(match)
        await session.flush()
    elif adopt:
        match.name = old.name
        match.color_index = old.color_index
    cache[old.id] = match.id
    return match.id


async def remap_transaction_categories_to_budget(
    session: AsyncSession,
    transactions: Sequence[Transaction],
    target_budget_id: uuid.UUID,
    *,
    adopt_names: bool = False,
) -> None:
    """Point moved transactions at categories of the target budget.

    A category is matched by translation_key (custom ones: by name); when the target has
    none, it is created there with the same name, parent, key, protection and a colour per
    the usual sibling rules. `adopt_names` (fresh budget
    seeded for the departing person): matched categories take the old name and colour. No moved operation loses its category.
    """
    if not transactions:
        return

    income_cache: dict[uuid.UUID, uuid.UUID] = {}
    expense_cache: dict[uuid.UUID, uuid.UUID] = {}

    for txn in transactions:
        if txn.income_category_id is not None:
            old_income = await session.get(IncomeCategory, txn.income_category_id)
            if old_income is not None:
                txn.income_category_id = await _resolve_income(
                    session, old_income, target_budget_id, income_cache, adopt_names
                )
        if txn.expense_category_id is not None:
            old_expense = await session.get(ExpenseCategory, txn.expense_category_id)
            if old_expense is not None:
                txn.expense_category_id = await _resolve_expense(
                    session, old_expense, target_budget_id, expense_cache, adopt_names
                )
