import uuid
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from app.models.income_category import IncomeCategory

CategoryKind = Literal["expense", "income"]

PALETTE_SIZE = 8
ALL_COLOR_INDICES = frozenset(range(1, PALETTE_SIZE + 1))


async def assign_category_color(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    *,
    kind: CategoryKind,
    parent_id: uuid.UUID | None = None,
) -> int:
    """Colour index unique among live siblings of the new category.

    Siblings: expense parents (parent_id is None) among the budget's parents;
    subcategories among the subcategories of one parent; income among income.
    First unused palette index; when all are taken, cycle by sibling count.
    """
    if kind == "income":
        model = IncomeCategory
        scope = [model.family_budget_id == family_budget_id]
    else:
        model = ExpenseCategory
        scope = [
            model.family_budget_id == family_budget_id,
            model.parent_id.is_(None)
            if parent_id is None
            else model.parent_id == parent_id,
        ]

    used = list(
        await session.scalars(
            select(model.color_index).where(model.is_deleted.is_(False), *scope)
        )
    )
    free = ALL_COLOR_INDICES - set(used)
    if free:
        return min(free)
    return len(used) % PALETTE_SIZE + 1
