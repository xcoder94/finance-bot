from datetime import date, datetime, timedelta
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


import pytest


@pytest.mark.parametrize(
    "text",
    [
        "kecha taksi 20 ming",
        "taksi 20 ming kecha",
        "Kecha taksi 20 ming",
        "кеча такси 20 минг",
        "такси 20 минг кеча",
    ],
)
def test_uz_kecha_is_yesterday(text):
    assert resolve_operation_date(text, now=NOW) == YESTERDAY


@pytest.mark.parametrize(
    "text",
    [
        "o'tgan kuni taksi 20 ming",
        "oʻtgan kuni taksi 20 ming",
        "o’tgan kuni taksi",
        "avval kuni taksi 20 ming",
        "ўтган куни такси 20 минг",
        "аввал куни такси 20 минг",
    ],
)
def test_uz_day_before_yesterday(text):
    assert resolve_operation_date(text, now=NOW) == date(2026, 8, 3)


@pytest.mark.parametrize("text", ["bugun taksi 20 ming", "бугун такси 20 минг"])
def test_uz_bugun_is_today(text):
    assert resolve_operation_date(text, now=NOW) == TODAY


def test_uz_date_words_stripped_from_comment():
    assert strip_date_words("kecha taksi", "kecha taksi 20 ming") == "taksi"
    assert strip_date_words("o'tgan kuni taksi", "o'tgan kuni taksi 20 ming") == "taksi"
    assert strip_date_words("bugun taksi", "bugun taksi 20 ming") == "taksi"
    assert strip_date_words("кеча такси", "кеча такси 20 минг") == "такси"


def test_uz_kechasi_not_a_date_word():
    assert resolve_operation_date("kechasi taksi 20 ming", now=NOW) == TODAY


@pytest.mark.parametrize(
    "text, days_back",
    [
        ("вчерашний такси 25 тысяч", 1),
        ("вчерашняя оплата 25 тысяч", 1),
        ("позавчерашний обед 50 тысяч", 2),
        ("kechagi taksi 20 ming", 1),
        ("кечаги такси 20 минг", 1),
        ("bugungi taksi 20 ming", 0),
        ("бугунги такси 20 минг", 0),
        ("сегодняшний обед 50 тысяч", 0),
    ],
)
def test_date_word_forms_resolve(text, days_back):
    assert resolve_operation_date(text, now=NOW) == TODAY - timedelta(days=days_back)


@pytest.mark.parametrize(
    "word", ["вчерашний", "вчерашняя", "позавчерашний", "сегодняшний", "kechagi", "кечаги", "bugungi", "бугунги"]
)
def test_date_word_forms_stripped_whole(word):
    assert strip_date_words(f"{word} такси", f"{word} такси 20 тысяч") == "такси"
