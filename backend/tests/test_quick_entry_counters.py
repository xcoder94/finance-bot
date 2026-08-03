from datetime import date
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from app.models.family_budget import FamilyBudget
from app.services.quick_entry_counters import (
    RefusalKind,
    can_model_call,
    can_unparsed,
    ensure_counters_day,
    should_spend_unparsed,
    spend_model_call,
    spend_unparsed,
    tashkent_today_for_counters,
)

TASHKENT = ZoneInfo("Asia/Tashkent")


def _budget(
    *,
    counters_day: date | None = None,
    daily_model_calls: int = 0,
    daily_unparsed: int = 0,
) -> FamilyBudget:
    return FamilyBudget(
        daily_model_calls=daily_model_calls,
        daily_unparsed=daily_unparsed,
        counters_day=counters_day,
    )


class TestEnsureCountersDay:
    def test_resets_on_new_day(self) -> None:
        budget = _budget(
            counters_day=date(2026, 8, 2),
            daily_model_calls=7,
            daily_unparsed=3,
        )
        ensure_counters_day(budget, date(2026, 8, 3))
        assert budget.counters_day == date(2026, 8, 3)
        assert budget.daily_model_calls == 0
        assert budget.daily_unparsed == 0

    def test_keeps_counters_same_day(self) -> None:
        budget = _budget(
            counters_day=date(2026, 8, 3),
            daily_model_calls=4,
            daily_unparsed=2,
        )
        ensure_counters_day(budget, date(2026, 8, 3))
        assert budget.daily_model_calls == 4
        assert budget.daily_unparsed == 2

    def test_initializes_when_counters_day_is_none(self) -> None:
        budget = _budget(daily_model_calls=1, daily_unparsed=1)
        ensure_counters_day(budget, date(2026, 8, 3))
        assert budget.counters_day == date(2026, 8, 3)
        assert budget.daily_model_calls == 0
        assert budget.daily_unparsed == 0


class TestTashkentMidnightBoundary:
    def test_tashkent_today_before_midnight(self) -> None:
        with patch("app.services.quick_entry_counters.datetime") as mock_dt:
            from datetime import datetime

            mock_dt.now.return_value = datetime(2026, 8, 3, 23, 59, tzinfo=TASHKENT)
            assert tashkent_today_for_counters() == date(2026, 8, 3)

    def test_tashkent_today_after_midnight(self) -> None:
        with patch("app.services.quick_entry_counters.datetime") as mock_dt:
            from datetime import datetime

            mock_dt.now.return_value = datetime(2026, 8, 4, 0, 1, tzinfo=TASHKENT)
            assert tashkent_today_for_counters() == date(2026, 8, 4)

    def test_counter_reset_across_tashkent_midnight(self) -> None:
        budget = _budget(
            counters_day=date(2026, 8, 3),
            daily_model_calls=50,
            daily_unparsed=20,
        )
        ensure_counters_day(budget, date(2026, 8, 4))
        assert budget.daily_model_calls == 0
        assert budget.daily_unparsed == 0


class TestSpendRules:
    def test_can_and_spend_model_call(self) -> None:
        budget = _budget(daily_model_calls=2)
        assert can_model_call(budget, 50) is True
        spend_model_call(budget)
        assert budget.daily_model_calls == 3
        assert can_model_call(budget, 3) is False

    def test_can_and_spend_unparsed(self) -> None:
        budget = _budget(daily_unparsed=19)
        assert can_unparsed(budget, 20) is True
        spend_unparsed(budget)
        assert budget.daily_unparsed == 20
        assert can_unparsed(budget, 20) is False


class TestUnparsedSpendPolicy:
    @pytest.mark.parametrize(
        "kind",
        [
            RefusalKind.NO_AMOUNT,
            RefusalKind.TOO_MANY_OPERATIONS,
            RefusalKind.CURRENCY_MISSING,
            RefusalKind.EMPTY_PARSE,
        ],
    )
    def test_common_refusals_spend_unparsed(self, kind: RefusalKind) -> None:
        assert should_spend_unparsed(kind) is True

    def test_model_failure_section_7_11_does_not_spend_unparsed(self) -> None:
        assert should_spend_unparsed(RefusalKind.MODEL_FAILURE) is False
