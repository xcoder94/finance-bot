"""Writes must not outlive the author's membership (ux-r14).

Joining or leaving a family moves the person's rows to another budget while holding his user
row FOR UPDATE (``lock_for_join`` / ``detach_member_to_own_budget``). A write that read the
person's budget just before that and saves just after lands in the old (deleted) budget and
is invisible in History while the wallet balance counts it.

``guard_family_unchanged`` takes FOR KEY SHARE on the user row first thing in every write:
it waits for a running membership change (a FOR UPDATE), never blocks other writes of the
same person (key-share locks are compatible) and does not conflict with ordinary updates of
the user row. If the budget changed, nothing is saved and ``FamilyChangedError`` (API: 409
``family_changed``) tells the client to reload and repeat. Lock order: person -> budgets.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family_budget import FamilyBudget
from app.models.user import User

FAMILY_CHANGED = "family_changed"


class FamilyChangedError(Exception):
    """The author moved to another budget while the write was in flight."""


async def guard_family_unchanged(session: AsyncSession, user: User) -> None:
    row = (
        await session.execute(
            select(User.family_budget_id, User.is_deleted)
            .where(User.id == user.id)
            .with_for_update(read=True, key_share=True)
        )
    ).first()
    seen: uuid.UUID = user.family_budget_id
    if row is None or row.is_deleted or row.family_budget_id != seen:
        raise FamilyChangedError()


async def budget_of_user(session: AsyncSession, user: User) -> FamilyBudget | None:
    """The person's budget. If it is gone because the person has just joined another family (the
    join deleted the old one while this message was already read), that is not "not registered":
    raise FamilyChangedError, the bot asks to repeat the message in the person's language."""
    budget = await session.get(FamilyBudget, user.family_budget_id)
    if budget is not None and not budget.is_deleted:
        return budget
    row = (
        await session.execute(
            select(User.family_budget_id, User.is_deleted).where(User.id == user.id)
        )
    ).first()
    if row is not None and not row.is_deleted and row.family_budget_id != user.family_budget_id:
        raise FamilyChangedError()
    return None
