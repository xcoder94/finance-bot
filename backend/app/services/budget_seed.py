import uuid
from calendar import monthrange
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.category_colors import assign_category_color

SEED_INCOME_CATEGORIES: list[tuple[str, str]] = [
    ("Зарплата", "salary"),
    ("Подработка", "side_job"),
    ("Подарки", "gifts"),
    ("Переводы от родных", "family_transfers"),
    ("Прочее", "income_other"),
]

SEED_EXPENSE_CATEGORIES: dict[str, tuple[str, list[tuple[str, str]]]] = {
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

PROTECTED_EXPENSE_PARENT_KEYS = frozenset({"food", "home", "health"})

SEED_WALLETS: list[tuple[str, str, str]] = [
    ("Наличный сум", "UZS", "cash_uzs"),
    ("Карта сум", "UZS", "card_uzs"),
    ("Наличный USD", "USD", "cash_usd"),
    ("Карта USD", "USD", "card_usd"),
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


async def copy_seed_categories_only(
    session: AsyncSession, family_budget_id: uuid.UUID
) -> None:
    for name, translation_key in SEED_INCOME_CATEGORIES:
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

    for parent_name, (parent_key, sub_entries) in SEED_EXPENSE_CATEGORIES.items():
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
                        session, family_budget_id, kind="expense"
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


def _split_amount(total: int, count: int) -> list[int]:
    base = total // count
    remainder = total % count
    return [base + (1 if index < remainder else 0) for index in range(count)]


def _previous_month_year_month() -> tuple[int, int]:
    now = datetime.now(UTC)
    if now.month == 1:
        return now.year - 1, 12
    return now.year, now.month - 1


def _demo_dates_in_month(
    count: int,
    year: int,
    month: int,
    *,
    early: bool = False,
    max_day: int | None = None,
) -> list[datetime]:
    _, days_in_month = monthrange(year, month)
    last_day = days_in_month if max_day is None else min(days_in_month, max_day)
    if last_day < 1:
        return []
    if count == 1:
        day = 3 if early else max(1, last_day // 2)
        day = min(day, last_day)
        return [datetime(year, month, day, 10, 0, tzinfo=UTC)]
    dates: list[datetime] = []
    for index in range(count):
        if count == 1:
            day = 1
        else:
            day = 1 + (index * (last_day - 1) // (count - 1))
        day = max(1, min(last_day, day))
        dates.append(datetime(year, month, day, 12, 0, tzinfo=UTC))
    return dates


def _scale_demo_count(count: int, elapsed_days: int, days_in_month: int) -> int:
    if count <= 0 or elapsed_days <= 0:
        return 0
    scaled = (count * elapsed_days + days_in_month // 2) // days_in_month
    return min(count, max(0, scaled))


def _scale_demo_total(total: int, elapsed_days: int, days_in_month: int) -> int:
    if total <= 0 or elapsed_days <= 0:
        return 0
    return (total * elapsed_days) // days_in_month


def _expected_partial_demo_row_count(elapsed_days: int, days_in_month: int) -> int:
    expense_counts = [4, 2, 1, 1, 3, 2, 1, 1, 2, 1]
    expense_totals = [
        2_200_000,
        600_000,
        900_000,
        250_000,
        700_000,
        900_000,
        450_000,
        1_000_000,
        150,
        350,
    ]
    income_counts = [1, 1, 1]
    income_totals = [8_000_000, 1_000_000, 600]
    rows = 0
    for count, total in zip(expense_counts, expense_totals, strict=True):
        if (
            _scale_demo_count(count, elapsed_days, days_in_month) > 0
            and _scale_demo_total(total, elapsed_days, days_in_month) > 0
        ):
            rows += _scale_demo_count(count, elapsed_days, days_in_month)
    for count, total in zip(income_counts, income_totals, strict=True):
        if (
            _scale_demo_count(count, elapsed_days, days_in_month) > 0
            and _scale_demo_total(total, elapsed_days, days_in_month) > 0
        ):
            rows += _scale_demo_count(count, elapsed_days, days_in_month)
    return rows


async def _wallet_by_translation_key(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    translation_key: str,
) -> Wallet | None:
    return await session.scalar(
        select(Wallet).where(
            Wallet.family_budget_id == family_budget_id,
            Wallet.translation_key == translation_key,
            Wallet.is_deleted.is_(False),
        )
    )


async def _expense_category_by_key(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    translation_key: str,
) -> ExpenseCategory | None:
    return await session.scalar(
        select(ExpenseCategory).where(
            ExpenseCategory.family_budget_id == family_budget_id,
            ExpenseCategory.translation_key == translation_key,
            ExpenseCategory.is_deleted.is_(False),
        )
    )


async def _income_category_by_key(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    translation_key: str,
) -> IncomeCategory | None:
    return await session.scalar(
        select(IncomeCategory).where(
            IncomeCategory.family_budget_id == family_budget_id,
            IncomeCategory.translation_key == translation_key,
            IncomeCategory.is_deleted.is_(False),
        )
    )


DEMO_EXPENSE_SPECS: list[tuple[str, int, int, str, list[str]]] = [
    ("groceries", 2_200_000, 4, "UZS", ["продукты", "супермаркет", "овощи", "бакалея"]),
    ("cafes_restaurants", 600_000, 2, "UZS", ["кафе", "ресторан"]),
    ("utilities", 900_000, 1, "UZS", ["коммунальные"]),
    ("telecom_internet", 250_000, 1, "UZS", ["интернет"]),
    ("taxi", 700_000, 3, "UZS", ["такси", "такси", "такси"]),
    ("fuel", 900_000, 2, "UZS", ["бензин", "АЗС"]),
    ("pharmacy", 450_000, 1, "UZS", ["аптека"]),
    ("clothing", 1_000_000, 1, "UZS", ["одежда"]),
    ("entertainment", 150, 2, "USD", ["кино", "концерт"]),
    ("repairs_furnishing", 350, 1, "USD", ["мебель"]),
]

DEMO_INCOME_SPECS: list[tuple[str, int, int, str, list[str], bool]] = [
    ("salary", 8_000_000, 1, "UZS", ["зарплата"], True),
    ("side_job", 1_000_000, 1, "UZS", ["подработка"], False),
    ("family_transfers", 600, 1, "USD", ["перевод"], False),
]


async def _seed_demo_month(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    *,
    year: int,
    month: int,
    card_uzs: Wallet,
    card_usd: Wallet,
    elapsed_days: int,
    max_day: int | None,
) -> None:
    _, days_in_month = monthrange(year, month)
    for key, total, count, currency, comments in DEMO_EXPENSE_SPECS:
        scaled_count = _scale_demo_count(count, elapsed_days, days_in_month)
        scaled_total = _scale_demo_total(total, elapsed_days, days_in_month)
        if scaled_count == 0 or scaled_total == 0:
            continue
        category = await _expense_category_by_key(session, family_budget_id, key)
        if category is None:
            continue
        wallet = card_uzs if currency == "UZS" else card_usd
        amounts = _split_amount(scaled_total, scaled_count)
        dates = _demo_dates_in_month(
            scaled_count, year, month, max_day=max_day
        )
        for index, amount in enumerate(amounts):
            session.add(
                Transaction(
                    family_budget_id=family_budget_id,
                    type="expense",
                    wallet_id=wallet.id,
                    amount=amount,
                    expense_category_id=category.id,
                    comment=comments[index % len(comments)],
                    created_by_user_id=created_by_user_id,
                    transaction_date=dates[index],
                    is_demo=True,
                )
            )

    for key, total, count, currency, comments, early in DEMO_INCOME_SPECS:
        scaled_count = _scale_demo_count(count, elapsed_days, days_in_month)
        scaled_total = _scale_demo_total(total, elapsed_days, days_in_month)
        if scaled_count == 0 or scaled_total == 0:
            continue
        category = await _income_category_by_key(session, family_budget_id, key)
        if category is None:
            continue
        wallet = card_uzs if currency == "UZS" else card_usd
        amounts = _split_amount(scaled_total, scaled_count)
        dates = _demo_dates_in_month(
            scaled_count, year, month, early=early, max_day=max_day
        )
        for index, amount in enumerate(amounts):
            session.add(
                Transaction(
                    family_budget_id=family_budget_id,
                    type="income",
                    wallet_id=wallet.id,
                    amount=amount,
                    income_category_id=category.id,
                    comment=comments[index % len(comments)],
                    created_by_user_id=created_by_user_id,
                    transaction_date=dates[index],
                    is_demo=True,
                )
            )


async def seed_demo_operations(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
) -> None:
    card_uzs = await _wallet_by_translation_key(session, family_budget_id, "card_uzs")
    card_usd = await _wallet_by_translation_key(session, family_budget_id, "card_usd")
    if card_uzs is None or card_usd is None:
        return

    prev_year, prev_month = _previous_month_year_month()
    _, prev_days = monthrange(prev_year, prev_month)
    await _seed_demo_month(
        session,
        family_budget_id,
        created_by_user_id,
        year=prev_year,
        month=prev_month,
        card_uzs=card_uzs,
        card_usd=card_usd,
        elapsed_days=prev_days,
        max_day=None,
    )

    now = datetime.now(UTC)
    cur_year, cur_month = now.year, now.month
    _, cur_days = monthrange(cur_year, cur_month)
    await _seed_demo_month(
        session,
        family_budget_id,
        created_by_user_id,
        year=cur_year,
        month=cur_month,
        card_uzs=card_uzs,
        card_usd=card_usd,
        elapsed_days=now.day,
        max_day=now.day,
    )


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
