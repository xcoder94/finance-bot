from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
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


# ---------------------------------------------------------------- payload v1 render
# Contract: work/db/m3-5-change-log.md. RU output must stay byte-identical to the
# frozen render_ru in alembic/versions/x4a5b6c7d8e9_change_log_payload.py.
MONTH_UZ: tuple[str, ...] = (
    "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
)
FIELD_LABEL_UZ: dict[str, str] = {
    "amount": "summa",
    "category": "toifa",
    "wallet": "hamyon",
    "date": "sana",
    "comment": "izoh",
    "from": "qayerdan",
    "to": "qayerga",
    "rate": "kurs",
}
FIELD_LABEL_RU: dict[str, str] = {
    "amount": FIELD_AMOUNT,
    "category": FIELD_CATEGORY,
    "wallet": FIELD_WALLET,
    "date": FIELD_DATE,
    "comment": FIELD_COMMENT,
    "from": FIELD_FROM,
    "to": FIELD_TO,
    "rate": FIELD_RATE,
}
ENTITY_FIELDS = ("category", "wallet", "from", "to")
# Uzbek names of default wallets/categories (frontend uz.json defaultEntities).
DEFAULT_ENTITY_UZ: dict[str, str] = {
    "card_uzs": "So'm kartasi", "cash_uzs": "Naqd so'm", "card_usd": "USD kartasi",
    "cash_usd": "Naqd USD", "salary": "Ish haqi", "side_job": "Qo'shimcha ish",
    "gifts": "Sovg'alar", "family_transfers": "Qarindoshlardan o'tkazmalar",
    "income_other": "Boshqa daromad", "food": "Ovqat", "groceries": "Oziq-ovqat",
    "cafes_restaurants": "Kafe va restoranlar", "delivery": "Yetkazib berish",
    "transport": "Transport", "taxi": "Taksi", "fuel": "Yoqilg'i",
    "public_transport": "Jamoat transporti", "car_maintenance": "Avtomobil xizmati",
    "home": "Uy", "rent": "Ijara", "utilities": "Kommunal xizmatlar",
    "telecom_internet": "Aloqa va internet", "repairs_furnishing": "Ta'mirlash va jihozlash",
    "children": "Bolalar", "kindergarten_school": "Bog'cha va maktab",
    "clubs_tutoring": "To'garaklar va repetitorlar", "kids_goods": "Bolalar mahsulotlari",
    "health": "Sog'liq", "pharmacy": "Dori-darmon va apteka",
    "doctors_clinics": "Shifokorlar va klinikalar", "dentistry": "Stomatologiya",
    "events_celebrations": "Tadbirlar va to'ylar", "toi_celebrations": "To'ylar va marosimlar",
    "event_gifts": "Sovg'alar", "shopping_leisure": "Xaridlar va dam olish",
    "clothing": "Kiyim", "entertainment": "Ko'ngilochar", "subscriptions": "Obunalar",
    "beauty_care": "Go'zallik va parvarish",
}


def _value_text(field: str, value: Any, lang: str) -> str:
    if value is None:
        return ""
    if field == "amount":
        return format_amount_text(int(value))
    if field == "date":
        return date.fromisoformat(value).strftime("%d.%m.%Y")
    if field in ENTITY_FIELDS:
        if lang == "uz" and value.get("tk") in DEFAULT_ENTITY_UZ:
            return DEFAULT_ENTITY_UZ[value["tk"]]
        return value["name"]
    return str(value)


def render_change_payload(payload: dict[str, Any], lang: str) -> str:
    """Render a v1 payload for the reader. Anything but 'uz' is Russian."""
    on = date.fromisoformat(payload["on"])
    actor = payload["actor"]["name"]
    uz = lang == "uz"
    head = f"{on.day}-{MONTH_UZ[on.month - 1]}" if uz else format_day_month(on)
    if payload["kind"] == "created":
        return f"{head} · {actor} yaratdi" if uz else f"{head} · создал {actor}"
    field = payload["field"]
    label = (FIELD_LABEL_UZ if uz else FIELD_LABEL_RU)[field]
    return (
        f"{head} · {actor}: {label} "
        f"{_value_text(field, payload['old'], lang)} → {_value_text(field, payload['new'], lang)}"
    )
