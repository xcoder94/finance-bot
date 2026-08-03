from datetime import date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.services.quick_entry_categories import strip_parent_category
from app.services.quick_entry_dates import (
    resolve_operation_date,
    strip_date_words,
    tashkent_today,
)

TASHKENT = ZoneInfo("Asia/Tashkent")

# Wednesday 2026-08-05 12:00 Asia/Tashkent
NOW = datetime(2026, 8, 5, 12, 0, tzinfo=TASHKENT)
TODAY = date(2026, 8, 5)
YESTERDAY = date(2026, 8, 4)
MONDAY = date(2026, 8, 3)


def test_tashkent_today_uses_tashkent_timezone():
    with patch("app.services.quick_entry_dates.datetime") as mock_dt:
        mock_dt.now.return_value = NOW
        assert tashkent_today() == TODAY


def test_vchera_returns_yesterday():
    assert resolve_operation_date("вчера такси 25 тысяч", now=NOW) == YESTERDAY


def test_pozavchera_returns_two_days_ago():
    assert resolve_operation_date("позавчера продукты", now=NOW) == date(2026, 8, 3)


def test_n_days_ago():
    assert resolve_operation_date("3 дня назад кофе", now=NOW) == date(2026, 8, 2)
    assert resolve_operation_date("5 дней назад кофе", now=NOW) == date(2026, 7, 31)


def test_weekday_most_recent_past_occurrence():
    assert resolve_operation_date("в понедельник такси", now=NOW) == MONDAY


def test_weekday_on_same_day_goes_to_previous_week():
    monday_now = datetime(2026, 8, 3, 12, 0, tzinfo=TASHKENT)
    assert resolve_operation_date("в понедельник такси", now=monday_now) == date(2026, 7, 27)


def test_proshlaya_pyatnitsa_goes_one_week_further():
    assert resolve_operation_date("в прошлую пятницу такси", now=NOW) == date(2026, 7, 24)


def test_40_days_ignored_returns_today():
    assert resolve_operation_date("40 дней назад такси", now=NOW) == TODAY


def test_future_date_clamped_to_today():
    thursday_now = datetime(2026, 8, 6, 12, 0, tzinfo=TASHKENT)
    # Without past-only rule this could be tomorrow; must stay today or past.
    result = resolve_operation_date("в пятницу такси", now=thursday_now)
    assert result <= date(2026, 8, 6)
    assert result == date(2026, 7, 31)


def test_no_date_marker_returns_today():
    assert resolve_operation_date("такси 25 тысяч", now=NOW) == TODAY


def test_strip_date_words_removes_vchera():
    assert strip_date_words("вчера такси", "вчера такси 25 тысяч") == "такси"


def test_strip_date_words_none_comment():
    assert strip_date_words(None, "вчера такси 25 тысяч") is None


def test_strip_date_words_truncates_to_200_chars():
    long_comment = "а" * 250
    result = strip_date_words(long_comment, "текст")
    assert result is not None
    assert len(result) == 200


def test_strip_parent_category():
    assert strip_parent_category("Транспорт: Такси") == "Такси"
    assert strip_parent_category("Транспорт：Такси") == "Такси"
    assert strip_parent_category("Такси") == "Такси"
    assert strip_parent_category(None) is None
    assert strip_parent_category("  Еда: Рестораны  ") == "Рестораны"
