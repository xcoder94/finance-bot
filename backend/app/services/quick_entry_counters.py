from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from zoneinfo import ZoneInfo

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family_budget import FamilyBudget

TASHKENT = ZoneInfo("Asia/Tashkent")


class RefusalKind(Enum):
    NO_AMOUNT = "no_amount"
    TOO_MANY_OPERATIONS = "too_many_operations"
    CURRENCY_MISSING = "currency_missing"
    EMPTY_PARSE = "empty_parse"
    MODEL_FAILURE = "model_failure"


def tashkent_today_for_counters() -> date:
    return datetime.now(TASHKENT).date()


async def ensure_counters_day(
    session: AsyncSession, budget: FamilyBudget, today: date
) -> None:
    """Reset the daily counters for a new day, atomically at the DB level.

    The conditional UPDATE (WHERE counters_day IS DISTINCT FROM :today) means a
    reset only ever applies once per day no matter how many concurrent requests
    race here; a request that loses the race simply no-ops and then refreshes
    its in-memory copy from the row another request already reset. This keeps
    the reset from clobbering a same-day increment written by a concurrent
    request between this request's check and its write.
    """
    if budget.counters_day == today:
        return
    stmt = (
        update(FamilyBudget)
        .where(
            FamilyBudget.id == budget.id,
            FamilyBudget.counters_day.is_distinct_from(today),
        )
        .values(counters_day=today, daily_model_calls=0, daily_unparsed=0)
    )
    await session.execute(stmt)
    await session.refresh(budget)


def can_model_call(budget: FamilyBudget, limit: int) -> bool:
    return budget.daily_model_calls < limit


def can_unparsed(budget: FamilyBudget, limit: int) -> bool:
    return budget.daily_unparsed < limit


async def spend_model_call(session: AsyncSession, budget: FamilyBudget) -> None:
    """Atomically increment daily_model_calls at the database level.

    `SET daily_model_calls = daily_model_calls + 1` is evaluated and written by
    the database in a single statement, so two concurrent increments against
    the same row can never both read the same "old" value and overwrite each
    other's write — the database serialises the two UPDATEs against the row.
    The in-memory `budget` object is refreshed afterwards so callers keep
    seeing a value consistent with what was actually persisted.

    NOTE: this increment is unconditional — it does not check the limit. Call
    sites that need "only increment if still under the limit" must use
    `try_spend_model_call` instead, which folds the check and the increment
    into a single atomic statement.
    """
    stmt = (
        update(FamilyBudget)
        .where(FamilyBudget.id == budget.id)
        .values(daily_model_calls=FamilyBudget.daily_model_calls + 1)
    )
    await session.execute(stmt)
    await session.refresh(budget)


async def try_spend_model_call(
    session: AsyncSession, budget: FamilyBudget, limit: int
) -> bool:
    """Atomically check-and-consume one daily model call.

    The check (`daily_model_calls < limit`) and the increment happen in one
    conditional UPDATE, so under concurrent requests only as many of them can
    succeed as there is remaining budget — the database, not two round trips
    of Python code, decides who gets the row. Returns True (call granted,
    counter incremented) or False (limit already reached, counter untouched).
    """
    stmt = (
        update(FamilyBudget)
        .where(
            FamilyBudget.id == budget.id,
            FamilyBudget.daily_model_calls < limit,
        )
        .values(daily_model_calls=FamilyBudget.daily_model_calls + 1)
    )
    result = await session.execute(stmt)
    await session.refresh(budget)
    return result.rowcount == 1


async def refund_model_call(session: AsyncSession, budget: FamilyBudget) -> None:
    """Undo a grant from `try_spend_model_call` for a call that, in the end,
    should not count against the daily limit (e.g. the parser call failed, or
    the business rule for this response says it is free).

    Guarded with `daily_model_calls > 0` so a refund can never push the
    counter negative even if it races a same-day reset.
    """
    stmt = (
        update(FamilyBudget)
        .where(
            FamilyBudget.id == budget.id,
            FamilyBudget.daily_model_calls > 0,
        )
        .values(daily_model_calls=FamilyBudget.daily_model_calls - 1)
    )
    await session.execute(stmt)
    await session.refresh(budget)


async def spend_unparsed(session: AsyncSession, budget: FamilyBudget) -> None:
    stmt = (
        update(FamilyBudget)
        .where(FamilyBudget.id == budget.id)
        .values(daily_unparsed=FamilyBudget.daily_unparsed + 1)
    )
    await session.execute(stmt)
    await session.refresh(budget)


def should_spend_unparsed(kind: RefusalKind) -> bool:
    return kind is not RefusalKind.MODEL_FAILURE
