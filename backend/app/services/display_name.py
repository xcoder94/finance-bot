"""Single rule for showing a wallet/category name (mirrors frontend getDisplayName).

translation_key is a permanent identity of a seeded entity and is never reset on rename.
An entity counts as "still default" only while its stored name equals the seeded name;
once the user renamed it, their own name is what everybody sees (and what goes to AI prompts),
and seed-only extras (cascade keywords) no longer apply.
"""

from __future__ import annotations

from app.services.budget_seed import (
    LEGACY_SEED_EXPENSE_CATEGORIES,
    LEGACY_SEED_INCOME_CATEGORIES,
    SEED_EXPENSE_CATEGORIES,
    SEED_INCOME_CATEGORIES,
    SEED_WALLETS,
)


def build_seed_name_by_key() -> dict[str, str]:
    """translation_key -> seeded RU name, for the current set AND the pre-U7 set (old budgets).

    A key that exists in both sets has the same name in both (guarded by a test)."""
    seed: dict[str, str] = {}
    for income, expense in (
        (LEGACY_SEED_INCOME_CATEGORIES, LEGACY_SEED_EXPENSE_CATEGORIES),
        (SEED_INCOME_CATEGORIES, SEED_EXPENSE_CATEGORIES),
    ):
        for name, key in income:
            seed[key] = name
        for parent_name, (parent_key, sub_entries) in expense.items():
            seed[parent_key] = parent_name
            for sub_name, sub_key in sub_entries:
                seed[sub_key] = sub_name
    for name, _currency, key in SEED_WALLETS:
        seed[key] = name
    return seed


_SEED_NAMES = build_seed_name_by_key()

# Uzbek texts of the seeded names; the same values as `defaultEntities` in the app's uz.json
# (a test compares them). Keys are translation_key.
SEED_NAMES_UZ: dict[str, str] = {
    "card_uzs": "So'm kartasi",
    "cash_uzs": "Naqd so'm",
    "card_usd": "USD kartasi",
    "cash_usd": "Naqd USD",
    "salary": "Ish haqi",
    "side_job": "Qo'shimcha ish",
    "gifts": "Sovg'alar",
    "family_transfers": "Qarindoshlardan o'tkazmalar",
    "income_other": "Boshqa daromad",
    "food": "Ovqat",
    "groceries": "Oziq-ovqat",
    "cafes_restaurants": "Kafe va restoranlar",
    "delivery": "Yetkazib berish",
    "transport": "Transport",
    "taxi": "Taksi",
    "fuel": "Yoqilg'i",
    "public_transport": "Jamoat transporti",
    "car_maintenance": "Avtomobil xizmati",
    "home": "Uy",
    "rent": "Ijara",
    "utilities": "Kommunal xizmatlar",
    "telecom_internet": "Aloqa va internet",
    "repairs_furnishing": "Ta'mirlash va jihozlash",
    "children": "Bolalar",
    "kindergarten_school": "Bog'cha va maktab",
    "clubs_tutoring": "To'garaklar va repetitorlar",
    "kids_goods": "Bolalar mahsulotlari",
    "health": "Sog'liq",
    "pharmacy": "Dorixona",
    "doctors_clinics": "Shifokorlar va klinikalar",
    "dentistry": "Stomatologiya",
    "events_celebrations": "To'y va tadbirlar",
    "toi_celebrations": "To'y va marosimlar",
    "event_gifts": "Sovg'alar",
    "shopping_leisure": "Shaxsiy va dam olish",
    "clothing": "Kiyim",
    "entertainment": "Ko'ngilochar",
    "subscriptions": "Obunalar",
    "beauty_care": "Go'zallik va parvarish",
    # keys of the set seeded into new budgets (PRD-ux U7; not yet in the app's uz.json)
    "cafes_delivery": "Kafe va yetkazib berish",
    "taxi_transit": "Taksi va yo'l haqi",
    "car": "Avtomobil",
    "utilities_telecom": "Kommunal va aloqa",
    "home_repairs": "Ta'mir va uy jihozlari",
    "kids_learning": "O'qish va to'garaklar",
    "drugstore": "Dorixona",
    "doctors": "Shifokorlar",
    "toi_gifts": "To'ylar va sovg'alar",
    "family_help": "Yaqinlarga yordam",
    "personal_leisure": "Shaxsiy va dam olish",
    "fun_subscriptions": "Ko'ngilochar va obunalar",
    "business_side_job": "Biznes va qo'shimcha ish",
    "transfers_gifts": "O'tkazmalar va sovg'alar",
}


def is_default_name(
    name: str,
    translation_key: str | None,
    seed_name_by_key: dict[str, str] | None = None,
) -> bool:
    if translation_key is None:
        return False
    seed = (seed_name_by_key or _SEED_NAMES).get(translation_key)
    return seed is not None and name.casefold() == seed.casefold()


def display_name(
    name: str,
    translation_key: str | None,
    seed_name_by_key: dict[str, str] | None = None,
    language: str = "ru",
) -> str:
    """Name to show to a person who reads `language` ("ru" / "uz").

    A seeded entity is localized only while its stored name is still a seeded name (ru, or
    already uz); once the user renamed it, their own name is what everybody sees.
    """
    seeds = seed_name_by_key or _SEED_NAMES
    if translation_key is None:
        return name
    seed_ru = seeds.get(translation_key)
    seed_uz = SEED_NAMES_UZ.get(translation_key)
    folded = name.casefold()
    is_default = (seed_ru is not None and folded == seed_ru.casefold()) or (
        seed_uz is not None and folded == seed_uz.casefold()
    )
    if not is_default:
        return name
    if language == "uz" and seed_uz is not None:
        return seed_uz
    return seed_ru if seed_ru is not None else name
