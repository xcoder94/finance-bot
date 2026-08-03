import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from app.models.income_category import IncomeCategory

CategoryKind = Literal["expense", "income"]

ALL_COLOR_INDICES = frozenset(range(1, 9))
RECENTLY_DELETED_WINDOW = timedelta(days=365)


async def assign_category_color(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    *,
    kind: CategoryKind,
) -> int:
    if kind == "income":
        model = IncomeCategory
    else:
        model = ExpenseCategory

    cutoff = datetime.now(UTC) - RECENTLY_DELETED_WINDOW

    active_colors = set(
        await session.scalars(
            select(model.color_index).where(
                model.family_budget_id == family_budget_id,
                model.is_deleted.is_(False),
            )
        )
    )

    recent_deleted_colors = set(
        await session.scalars(
            select(model.color_index).where(
                model.family_budget_id == family_budget_id,
                model.is_deleted.is_(True),
                model.deleted_at.is_not(None),
                model.deleted_at >= cutoff,
            )
        )
    )

    free = ALL_COLOR_INDICES - active_colors - recent_deleted_colors
    if free:
        return min(free)

    oldest_color = await session.scalar(
        select(model.color_index)
        .where(
            model.family_budget_id == family_budget_id,
            model.is_deleted.is_(True),
            model.deleted_at.is_not(None),
        )
        .order_by(model.deleted_at.asc())
        .limit(1)
    )
    if oldest_color is not None:
        return oldest_color

    return min(ALL_COLOR_INDICES - active_colors) if ALL_COLOR_INDICES - active_colors else 1
