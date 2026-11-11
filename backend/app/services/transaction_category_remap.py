import datetime
import logging
import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.services.budget_seed import LEGACY_TO_NEW_KEY, NEW_TO_LEGACY_KEY, PARENT_FALLBACK
from app.services.category_colors import assign_category_color


logger = logging.getLogger(__name__)


def _fold(name: str) -> str:
    return name.strip().casefold()


def _candidate_keys(key: str) -> list[str]:
    """The key itself first, then its successor in the other seed set (PRD-ux U7 merge table)."""
    keys = [key]
    for table in (LEGACY_TO_NEW_KEY, NEW_TO_LEGACY_KEY):
        if key in table:
            keys.append(table[key])
    return keys


def _best(rows: list):
    """Several rows may carry the same identity in budgets made by older code: live first, then oldest."""
    return min(rows, key=lambda c: (c.is_deleted, c.created_at)) if rows else None


def _pick(candidates: list, old):
    """Target category with the same identity as `old`. Liveness is NOT part of identity: whether a
    row is deleted is the target budget's own decision, so a deleted row matches as well as a live one.
    Seed category: its key, then successor keys in the other seed set. Custom: folded name."""
    if old.translation_key is not None:
        for key in _candidate_keys(old.translation_key):
            hit = _best([c for c in candidates if c.translation_key == key])
            if hit is not None:
                return hit
        return None
    return _best([c for c in candidates if _fold(c.name) == _fold(old.name)])


def _created_state(old, *, fresh: bool, parent_deleted: bool) -> tuple[bool, datetime.datetime | None]:
    """Liveness of a row created by the remap. Joining: the joiner's own deletion travels, and a row
    never lives under a deleted parent. Leaving (fresh budget): live, unless the parent is deleted."""
    deleted = (old.is_deleted and not fresh) or parent_deleted
    if not deleted:
        return False, None
    return True, old.deleted_at or datetime.datetime.now(datetime.UTC)


async def _resolve_income(
    session: AsyncSession,
    old: IncomeCategory,
    target_budget_id: uuid.UUID,
    cache: dict[uuid.UUID, uuid.UUID],
    fresh: bool = False,
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
            )
        )
    ).all()
    match = _pick(list(candidates), old)
    if match is None:
        if old.translation_key is not None:
            logger.warning("seed key created on remap: income %s", old.translation_key)
        is_deleted, deleted_at = _created_state(old, fresh=fresh, parent_deleted=False)
        match = IncomeCategory(
            family_budget_id=target_budget_id,
            name=old.name,
            translation_key=old.translation_key,
            color_index=await assign_category_color(session, target_budget_id, kind="income"),
            is_deleted=is_deleted,
            deleted_at=deleted_at,
        )
        session.add(match)
        await session.flush()
    elif fresh and match.translation_key == old.translation_key:
        match.name = old.name
        match.color_index = old.color_index
    cache[old.id] = match.id
    return match.id


async def _resolve_expense(
    session: AsyncSession,
    old: ExpenseCategory,
    target_budget_id: uuid.UUID,
    cache: dict[uuid.UUID, uuid.UUID],
    fresh: bool = False,
) -> uuid.UUID:
    if old.id in cache:
        return cache[old.id]
    if old.family_budget_id == target_budget_id:
        cache[old.id] = old.id
        return old.id

    target_parent_id: uuid.UUID | None = None
    parent_deleted = False
    if old.parent_id is not None:
        old_parent = await session.get(ExpenseCategory, old.parent_id)
        if old_parent is not None:
            target_parent_id = await _resolve_expense(
                session, old_parent, target_budget_id, cache, fresh
            )
            target_parent = await session.get(ExpenseCategory, target_parent_id)
            parent_deleted = target_parent is not None and target_parent.is_deleted

    if old.translation_key is not None:
        # a seed key identifies the row by itself: search the whole budget, ignore parent and state
        stmt = select(ExpenseCategory).where(ExpenseCategory.family_budget_id == target_budget_id)
    else:
        stmt = select(ExpenseCategory).where(
            ExpenseCategory.family_budget_id == target_budget_id,
            ExpenseCategory.parent_id.is_(None)
            if target_parent_id is None
            else ExpenseCategory.parent_id == target_parent_id,
        )
    match = _pick(list((await session.scalars(stmt)).all()), old)
    if match is None and old.translation_key in PARENT_FALLBACK and target_parent_id is not None:
        # seed sub-category with no counterpart in the target set: the operation lies on the parent,
        # in whatever state the target budget keeps it
        cache[old.id] = target_parent_id
        return target_parent_id
    if match is None:
        if old.translation_key is not None:
            logger.warning("seed key created on remap: %s", old.translation_key)
        is_deleted, deleted_at = _created_state(old, fresh=fresh, parent_deleted=parent_deleted)
        match = ExpenseCategory(
            family_budget_id=target_budget_id,
            name=old.name,
            translation_key=old.translation_key,
            parent_id=target_parent_id,
            is_protected=old.is_protected,
            color_index=await assign_category_color(
                session, target_budget_id, kind="expense", parent_id=target_parent_id
            ),
            is_deleted=is_deleted,
            deleted_at=deleted_at,
        )
        session.add(match)
        await session.flush()
    elif fresh and match.translation_key == old.translation_key:
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

    Identity, not state: a category is matched by translation_key (then its successor key in the
    other seed set, budget_seed.LEGACY_TO_NEW_KEY / NEW_TO_LEGACY_KEY) over the whole target
    budget; a custom one by name under the resolved parent. Whether the matched row is deleted is
    the target budget's decision and is never changed; the operation keeps that row. A seed
    sub-category without a counterpart (PARENT_FALLBACK) goes to its parent.
    Rows are created only for the person's own custom categories (and, for old mixed budgets, a
    missing seed key). Joining: the created row is deleted if the person deleted it or if its parent
    is deleted in the target. `adopt_names` marks leaving into a fresh budget: created rows are live
    (unless the parent is deleted) and matched seed rows take the old name and colour.
    No moved operation loses its category.
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
