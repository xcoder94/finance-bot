import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.services.budget_seed import LEGACY_TO_NEW_KEY, NEW_TO_LEGACY_KEY, PARENT_FALLBACK
from app.services.category_colors import assign_category_color


def _fold(name: str) -> str:
    return name.strip().casefold()


def _candidate_keys(key: str) -> list[str]:
    """The key itself first, then its successor in the other seed set (PRD-ux U7 merge table)."""
    keys = [key]
    for table in (LEGACY_TO_NEW_KEY, NEW_TO_LEGACY_KEY):
        if key in table:
            keys.append(table[key])
    return keys


def _pick(candidates: list, old):
    """First target category matching the old one: by key (then successor keys), custom by name."""
    if old.translation_key is not None:
        for key in _candidate_keys(old.translation_key):
            hit = next((c for c in candidates if c.translation_key == key), None)
            if hit is not None:
                return hit
        return None
    return next(
        (c for c in candidates if c.translation_key is None and _fold(c.name) == _fold(old.name)),
        None,
    )


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
    candidates = (
        await session.scalars(
            select(IncomeCategory).where(
                IncomeCategory.family_budget_id == target_budget_id,
                IncomeCategory.is_deleted.is_(old.is_deleted),
            )
        )
    ).all()
    match = _pick(list(candidates), old)
    if match is None:
        match = IncomeCategory(
            family_budget_id=target_budget_id,
            name=old.name,
            translation_key=old.translation_key,
            color_index=await assign_category_color(session, target_budget_id, kind="income"),
            is_deleted=old.is_deleted,
            deleted_at=old.deleted_at,
        )
        session.add(match)
        await session.flush()
    elif adopt and match.translation_key == old.translation_key:
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

    candidates = (
        await session.scalars(
            select(ExpenseCategory).where(
                ExpenseCategory.family_budget_id == target_budget_id,
                ExpenseCategory.is_deleted.is_(old.is_deleted),
                ExpenseCategory.parent_id.is_(None)
                if target_parent_id is None
                else ExpenseCategory.parent_id == target_parent_id,
            )
        )
    ).all()
    match = _pick(list(candidates), old)
    if (
        match is None
        and old.translation_key in PARENT_FALLBACK
        and target_parent_id is not None
        and not old.is_deleted
    ):
        # seed sub-category with no counterpart in the target set: nearest parent
        parent_live = await session.get(ExpenseCategory, target_parent_id)
        if parent_live is not None and not parent_live.is_deleted:
            cache[old.id] = target_parent_id
            return target_parent_id
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
            is_deleted=old.is_deleted,
            deleted_at=old.deleted_at,
        )
        session.add(match)
        await session.flush()
    elif adopt and match.translation_key == old.translation_key:
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

    A category is matched by translation_key, then by its successor key in the other seed set
    (budget_seed.LEGACY_TO_NEW_KEY / NEW_TO_LEGACY_KEY); custom ones by name. A deleted category
    is matched only among deleted ones and is created deleted, so it never comes back to life.
    When the target has none, the category is created there with the same name, parent, key, protection and a colour per
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
