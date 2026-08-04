from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.services.change_log_format import (
    FIELD_AMOUNT,
    MONTH_GENITIVE,
    change_line,
    creation_line,
    format_amount_text,
    format_day_month,
    format_rate_text,
    format_transaction_date_text,
)

TASHKENT = ZoneInfo("Asia/Tashkent")


def test_month_genitive_exact():
    assert MONTH_GENITIVE == (
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря",
    )


def test_creation_and_change_lines_match_prd():
    assert creation_line(created_on=date(2026, 8, 1), creator_name="Рустам") == (
        "1 августа · создал Рустам"
    )
    assert change_line(
        edited_on=date(2026, 8, 2),
        editor_name="Дилноза",
        field_label=FIELD_AMOUNT,
        old_value="20 000",
        new_value="200 000",
    ) == "2 августа · Дилноза: сумма 20 000 → 200 000"
    assert "→" in change_line(
        edited_on=date(2026, 8, 2),
        editor_name="Дилноза",
        field_label="категория",
        old_value="Продукты",
        new_value="Такси",
    )
    assert " · " in creation_line(created_on=date(2026, 1, 1), creator_name="A")


def test_amount_date_rate_helpers():
    assert format_amount_text(20_000) == "20 000"
    assert format_amount_text(200_000) == "200 000"
    assert format_day_month(date(2026, 8, 1)) == "1 августа"
    dt = datetime(2026, 8, 29, 10, 0, tzinfo=TASHKENT)
    assert format_transaction_date_text(dt) == "29.08.2026"
    assert format_rate_text(Decimal("12800")) == "12800"
    assert format_rate_text(Decimal("12.50")) == "12.5"
