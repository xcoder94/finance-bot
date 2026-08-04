from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

TASHKENT = ZoneInfo("Asia/Tashkent")

MONTH_GENITIVE: tuple[str, ...] = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)

FIELD_AMOUNT = "сумма"
FIELD_CATEGORY = "категория"
FIELD_WALLET = "кошелёк"
FIELD_DATE = "дата"
FIELD_COMMENT = "комментарий"
FIELD_FROM = "откуда"
FIELD_TO = "куда"
FIELD_RATE = "курс"


def format_day_month(d: date) -> str:
    return f"{d.day} {MONTH_GENITIVE[d.month - 1]}"


def format_amount_text(amount: int) -> str:
    negative = amount < 0
    digits = str(abs(amount))
    groups: list[str] = []
    while digits:
        groups.insert(0, digits[-3:])
        digits = digits[:-3]
    formatted = " ".join(groups)
    return f"-{formatted}" if negative else formatted


def format_transaction_date_text(dt: datetime) -> str:
    local = dt.astimezone(TASHKENT)
    return local.strftime("%d.%m.%Y")


def format_rate_text(rate: Decimal) -> str:
    normalized = rate.normalize()
    if normalized == normalized.to_integral_value():
        return str(int(normalized))
    text = format(normalized, "f")
    return text.rstrip("0").rstrip(".")


def creation_line(*, created_on: date, creator_name: str) -> str:
    return f"{format_day_month(created_on)} · создал {creator_name}"


def change_line(
    *,
    edited_on: date,
    editor_name: str,
    field_label: str,
    old_value: str,
    new_value: str,
) -> str:
    return (
        f"{format_day_month(edited_on)} · {editor_name}: "
        f"{field_label} {old_value} → {new_value}"
    )
