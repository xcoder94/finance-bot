import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.income_category import IncomeCategory
from app.models.user import User
from app.models.wallet import Wallet
from app.services.category_colors import assign_category_color

LEGACY_SEED_INCOME_CATEGORIES: list[tuple[str, str]] = [
    ("Зарплата", "salary"),
    ("Подработка", "side_job"),
    ("Подарки", "gifts"),
    ("Переводы от родных", "family_transfers"),
    ("Прочее", "income_other"),
]

LEGACY_SEED_EXPENSE_CATEGORIES: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "Еда": (
        "food",
        [
            ("Продукты", "groceries"),
            ("Кафе и рестораны", "cafes_restaurants"),
            ("Доставка", "delivery"),
        ],
    ),
    "Транспорт": (
        "transport",
        [
            ("Такси", "taxi"),
            ("Топливо", "fuel"),
            ("Общественный транспорт", "public_transport"),
            ("Обслуживание авто", "car_maintenance"),
        ],
    ),
    "Дом": (
        "home",
        [
            ("Аренда", "rent"),
            ("Коммунальные услуги", "utilities"),
            ("Связь и интернет", "telecom_internet"),
            ("Ремонт и обустройство", "repairs_furnishing"),
        ],
    ),
    "Дети": (
        "children",
        [
            ("Садик и школа", "kindergarten_school"),
            ("Кружки и репетиторы", "clubs_tutoring"),
            ("Детские товары", "kids_goods"),
        ],
    ),
    "Здоровье": (
        "health",
        [
            ("Лекарства и аптека", "pharmacy"),
            ("Врачи и клиники", "doctors_clinics"),
            ("Стоматология", "dentistry"),
        ],
    ),
    "События и тои": (
        "events_celebrations",
        [
            ("Тои и маърака", "toi_celebrations"),
            ("Подарки", "event_gifts"),
        ],
    ),
    "Покупки и досуг": (
        "shopping_leisure",
        [
            ("Одежда", "clothing"),
            ("Развлечения", "entertainment"),
            ("Подписки", "subscriptions"),
            ("Красота и уход", "beauty_care"),
        ],
    ),
}

# Set seeded into NEW budgets (PRD-ux U7): 7 parents / 17 subcategories / 4 income.
# Budgets created earlier keep the LEGACY_* set (PRD §15.5, no migration); their translation
# keys stay known to display_name and the cascade keywords.
SEED_INCOME_CATEGORIES: list[tuple[str, str]] = [
    ("Зарплата", "salary"),
    ("Бизнес и подработка", "business_side_job"),
    ("Переводы и подарки", "transfers_gifts"),
    ("Прочее", "income_other"),
]

SEED_EXPENSE_CATEGORIES: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "Еда": (
        "food",
        [
            ("Продукты", "groceries"),
            ("Кафе и доставка", "cafes_delivery"),
        ],
    ),
    "Транспорт": (
        "transport",
        [
            ("Такси и проезд", "taxi_transit"),
            ("Автомобиль", "car"),
        ],
    ),
    "Дом": (
        "home",
        [
            ("Аренда", "rent"),
            ("Коммуналка и связь", "utilities_telecom"),
            ("Ремонт и вещи для дома", "home_repairs"),
        ],
    ),
    "Дети": (
        "children",
        [
            ("Учёба и кружки", "kids_learning"),
            ("Детские товары", "kids_goods"),
        ],
    ),
    "Здоровье": (
        "health",
        [
            ("Аптека", "drugstore"),
            ("Врачи", "doctors"),
        ],
    ),
    "Тои и подарки": (
        "toi_gifts",
        [
            ("Тои и маърака", "toi_celebrations"),
            ("Подарки", "event_gifts"),
            ("Помощь родным", "family_help"),
        ],
    ),
    "Личное и досуг": (
        "personal_leisure",
        [
            ("Одежда", "clothing"),
            ("Красота и уход", "beauty_care"),
            ("Развлечения и подписки", "fun_subscriptions"),
        ],
    ),
}

# Key successor tables used when operations move between budgets (join / leave / delete).
# Only keys that exist in one set alone are listed; keys shared by both sets map to themselves.
# LEGACY_TO_NEW_KEY: a legacy-only key -> the key that absorbed it in the new set.
LEGACY_TO_NEW_KEY: dict[str, str] = {
    "side_job": "business_side_job",
    "gifts": "transfers_gifts",
    "family_transfers": "transfers_gifts",
    "cafes_restaurants": "cafes_delivery",
    "delivery": "cafes_delivery",
    "taxi": "taxi_transit",
    "public_transport": "taxi_transit",
    "fuel": "car",
    "car_maintenance": "car",
    "utilities": "utilities_telecom",
    "telecom_internet": "utilities_telecom",
    "repairs_furnishing": "home_repairs",
    "kindergarten_school": "kids_learning",
    "clubs_tutoring": "kids_learning",
    "pharmacy": "drugstore",
    "doctors_clinics": "doctors",
    "dentistry": "doctors",
    "events_celebrations": "toi_gifts",
    "shopping_leisure": "personal_leisure",
    "entertainment": "fun_subscriptions",
    "subscriptions": "fun_subscriptions",
}
# NEW_TO_LEGACY_KEY: a new-only key -> the closest single legacy key (when several were merged,
# the first of them / the main one).
NEW_TO_LEGACY_KEY: dict[str, str] = {
    "business_side_job": "side_job",
    "transfers_gifts": "family_transfers",
    "cafes_delivery": "cafes_restaurants",
    "taxi_transit": "taxi",
    "car": "fuel",
    "utilities_telecom": "utilities",
    "home_repairs": "repairs_furnishing",
    "kids_learning": "kindergarten_school",
    "drugstore": "pharmacy",
    "doctors": "doctors_clinics",
    "toi_gifts": "events_celebrations",
    "personal_leisure": "shopping_leisure",
    "fun_subscriptions": "entertainment",
}
# New-only keys with no legacy counterpart: the operation goes to the nearest parent.
PARENT_FALLBACK = frozenset({"family_help"})

PROTECTED_EXPENSE_PARENT_KEYS = frozenset({"food", "home", "health"})

SEED_WALLETS: list[tuple[str, str, str]] = [
    ("Наличный сум", "UZS", "cash_uzs"),
    ("Карта сум", "UZS", "card_uzs"),
]


async def assign_default_card_uzs(session: AsyncSession, user: User) -> None:
    stmt = select(Wallet).where(
        Wallet.family_budget_id == user.family_budget_id,
        Wallet.name == "Карта сум",
        Wallet.is_deleted.is_(False),
        Wallet.is_personal.is_(False),
    )
    wallet = await session.scalar(stmt)
    if wallet is not None:
        user.default_wallet_id = wallet.id


LEGACY_ONLY_KEYS = frozenset(
    {key for _n, key in LEGACY_SEED_INCOME_CATEGORIES}
    | {k for _p, (_pk, subs) in LEGACY_SEED_EXPENSE_CATEGORIES.items() for _sn, k in subs}
    | {pk for _p, (pk, _s) in LEGACY_SEED_EXPENSE_CATEGORIES.items()}
) - frozenset(
    {key for _n, key in SEED_INCOME_CATEGORIES}
    | {k for _p, (_pk, subs) in SEED_EXPENSE_CATEGORIES.items() for _sn, k in subs}
    | {pk for _p, (pk, _s) in SEED_EXPENSE_CATEGORIES.items()}
)


_NEW_ONLY_KEYS = (
    frozenset(
        {key for _n, key in SEED_INCOME_CATEGORIES}
        | {k for _p, (pk, subs) in SEED_EXPENSE_CATEGORIES.items() for _sn, k in subs}
        | {pk for _p, (pk, _subs) in SEED_EXPENSE_CATEGORIES.items()}
    )
    - frozenset(
        {key for _n, key in LEGACY_SEED_INCOME_CATEGORIES}
        | {k for _p, (_pk, subs) in LEGACY_SEED_EXPENSE_CATEGORIES.items() for _sn, k in subs}
        | {pk for _p, (pk, _subs) in LEGACY_SEED_EXPENSE_CATEGORIES.items()}
    )
)


async def _has_key(
    session: AsyncSession, family_budget_id: uuid.UUID, keys: frozenset[str], *, live_only: bool
) -> bool:
    for model in (ExpenseCategory, IncomeCategory):
        stmt = select(model.id).where(
            model.family_budget_id == family_budget_id, model.translation_key.in_(keys)
        )
        if live_only:
            stmt = stmt.where(model.is_deleted.is_(False))
        if await session.scalar(stmt.limit(1)) is not None:
            return True
    return False


async def budget_uses_legacy_set(session: AsyncSession, family_budget_id: uuid.UUID) -> bool:
    """True when the budget actually uses the pre-U7 category set: live legacy-only seed keys
    and no live new-only ones. A mixed budget (made by older join code) counts as the new set;
    with no live seed keys at all, any legacy-only key (even deleted) decides."""
    legacy_live = await _has_key(session, family_budget_id, LEGACY_ONLY_KEYS, live_only=True)
    new_live = await _has_key(session, family_budget_id, _NEW_ONLY_KEYS, live_only=True)
    if legacy_live or new_live:
        return legacy_live and not new_live
    return await _has_key(session, family_budget_id, LEGACY_ONLY_KEYS, live_only=False)


async def copy_seed_categories_only(
    session: AsyncSession, family_budget_id: uuid.UUID, *, legacy: bool = False
) -> None:
    """Seed the categories of a new budget. `legacy=True` seeds the pre-U7 set (tests of
    old budgets only; production code always seeds the current set)."""
    income_seed = LEGACY_SEED_INCOME_CATEGORIES if legacy else SEED_INCOME_CATEGORIES
    expense_seed = LEGACY_SEED_EXPENSE_CATEGORIES if legacy else SEED_EXPENSE_CATEGORIES
    for name, translation_key in income_seed:
        session.add(
            IncomeCategory(
                family_budget_id=family_budget_id,
                name=name,
                translation_key=translation_key,
                color_index=await assign_category_color(
                    session, family_budget_id, kind="income"
                ),
            )
        )

    for parent_name, (parent_key, sub_entries) in expense_seed.items():
        parent = ExpenseCategory(
            family_budget_id=family_budget_id,
            name=parent_name,
            parent_id=None,
            translation_key=parent_key,
            is_protected=parent_key in PROTECTED_EXPENSE_PARENT_KEYS,
            color_index=await assign_category_color(
                session, family_budget_id, kind="expense"
            ),
        )
        session.add(parent)
        await session.flush()
        for sub_name, sub_key in sub_entries:
            session.add(
                ExpenseCategory(
                    family_budget_id=family_budget_id,
                    name=sub_name,
                    parent_id=parent.id,
                    translation_key=sub_key,
                    color_index=await assign_category_color(
                        session,
                        family_budget_id,
                        kind="expense",
                        parent_id=parent.id,
                    ),
                )
            )


async def copy_seed_wallets_only(
    session: AsyncSession, family_budget_id: uuid.UUID
) -> None:
    for name, currency, translation_key in SEED_WALLETS:
        session.add(
            Wallet(
                family_budget_id=family_budget_id,
                name=name,
                currency=currency,
                translation_key=translation_key,
                is_personal=False,
            )
        )


async def copy_seed_data(session: AsyncSession, family_budget_id: uuid.UUID) -> None:
    await copy_seed_categories_only(session, family_budget_id)
    await copy_seed_wallets_only(session, family_budget_id)


async def count_seed_rows(
    session: AsyncSession, family_budget_id: uuid.UUID
) -> dict[str, int]:
    wallet_count = await session.scalar(
        select(func.count())
        .select_from(Wallet)
        .where(Wallet.family_budget_id == family_budget_id, Wallet.is_deleted.is_(False))
    )
    income_count = await session.scalar(
        select(func.count())
        .select_from(IncomeCategory)
        .where(
            IncomeCategory.family_budget_id == family_budget_id,
            IncomeCategory.is_deleted.is_(False),
        )
    )
    expense_top_count = await session.scalar(
        select(func.count())
        .select_from(ExpenseCategory)
        .where(
            ExpenseCategory.family_budget_id == family_budget_id,
            ExpenseCategory.parent_id.is_(None),
            ExpenseCategory.is_deleted.is_(False),
        )
    )
    expense_sub_count = await session.scalar(
        select(func.count())
        .select_from(ExpenseCategory)
        .where(
            ExpenseCategory.family_budget_id == family_budget_id,
            ExpenseCategory.parent_id.is_not(None),
            ExpenseCategory.is_deleted.is_(False),
        )
    )
    return {
        "wallets": wallet_count or 0,
        "income_categories": income_count or 0,
        "expense_top_level": expense_top_count or 0,
        "expense_subcategories": expense_sub_count or 0,
    }
