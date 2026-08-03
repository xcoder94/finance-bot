from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from zoneinfo import ZoneInfo

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


def ensure_counters_day(budget: FamilyBudget, today: date) -> None:
    if budget.counters_day == today:
        return
    budget.counters_day = today
    budget.daily_model_calls = 0
    budget.daily_unparsed = 0


def can_model_call(budget: FamilyBudget, limit: int) -> bool:
    return budget.daily_model_calls < limit


def can_unparsed(budget: FamilyBudget, limit: int) -> bool:
    return budget.daily_unparsed < limit


def spend_model_call(budget: FamilyBudget) -> None:
    budget.daily_model_calls += 1


def spend_unparsed(budget: FamilyBudget) -> None:
    budget.daily_unparsed += 1


def should_spend_unparsed(kind: RefusalKind) -> bool:
    return kind is not RefusalKind.MODEL_FAILURE
