import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import case, func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.expense_category import ExpenseCategory
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.history_analytics import (
    CategoryAmount,
    CurrencyBalance,
    HistoryItem,
    PerCurrencySummary,
    PersonalPerCurrencySummary,
    PersonalSummaryResponse,
    PersonalWalletBalancesResponse,
    SubcategoryAmount,
    SummaryResponse,
    TrendEntry,
    WalletBalancesResponse,
)
from app.services.wallet_visibility import personal_ops_hidden_clause
from app.services.wallets_categories import get_expense_parent_including_deleted
from app.services.member_texts import departed_label

TASHKENT = ZoneInfo("Asia/Tashkent")


def default_calendar_year_range(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.now(UTC)
    date_from = datetime(now.year, 1, 1, tzinfo=UTC)
    date_to = datetime(now.year, 12, 31, 23, 59, 59, 999999, tzinfo=UTC)
    return date_from, date_to


def resolve_analytics_date_range(
    date_from: datetime | None,
    date_to: datetime | None,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    if date_from is None and date_to is None:
        return default_calendar_year_range(now)
    if date_from is None or date_to is None:
        raise HTTPException(status_code=422, detail="date_from and date_to must both be provided or both omitted")
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to")
    return date_from, date_to


async def count_family_users(session: AsyncSession, family_budget_id: uuid.UUID) -> int:
    stmt = select(func.count()).select_from(User).where(User.family_budget_id == family_budget_id)
    return int(await session.scalar(stmt) or 0)


async def count_active_family_members(
    session: AsyncSession, family_budget_id: uuid.UUID
) -> int:
    stmt = (
        select(func.count())
        .select_from(User)
        .where(
            User.family_budget_id == family_budget_id,
            User.is_deleted.is_(False),
        )
    )
    return int(await session.scalar(stmt) or 0)


def _resolve_display_name(user: User) -> str:
    return user.first_name or user.username or "Unknown"


def format_history_author(
    user: User | None, *, family_budget_id: uuid.UUID
) -> str | None:
    if user is None:
        return "Unknown"
    name = _resolve_display_name(user)
    if user.family_budget_id != family_budget_id or user.is_deleted:
        return departed_label(name)
    return name


async def _has_departed_transaction_authors(
    session: AsyncSession, family_budget_id: uuid.UUID
) -> bool:
    active_member_ids = select(User.id).where(
        User.family_budget_id == family_budget_id,
        User.is_deleted.is_(False),
    )
    stmt = (
        select(func.count())
        .select_from(Transaction)
        .where(
            Transaction.family_budget_id == family_budget_id,
            Transaction.is_deleted.is_(False),
            Transaction.created_by_user_id.not_in(active_member_ids),
        )
        .limit(1)
    )
    return int(await session.scalar(stmt) or 0) > 0


async def should_include_created_by(session: AsyncSession, family_budget_id: uuid.UUID) -> bool:
    if await count_active_family_members(session, family_budget_id) >= 2:
        return True
    if await count_family_users(session, family_budget_id) >= 2:
        return True
    return await _has_departed_transaction_authors(session, family_budget_id)


def tashkent_today(now: datetime) -> datetime.date:
    return now.astimezone(TASHKENT).date()


def weekday_occurrence_counts(
    date_from: datetime, date_to: datetime, now: datetime
) -> list[int]:
    start = date_from.date()
    end = min(date_to.date(), tashkent_today(now))
    counts = [0, 0, 0, 0, 0, 0, 0]
    if end < start:
        return counts
    current = start
    while current <= end:
        counts[current.weekday()] += 1
        current += timedelta(days=1)
    return counts


def expense_weekday_averages(
    sums_by_currency: dict[str, list[int]],
    date_from: datetime,
    date_to: datetime,
    now: datetime,
) -> dict[str, list[int]]:
    counts = weekday_occurrence_counts(date_from, date_to, now)
    averages: dict[str, list[int]] = {}
    for currency, sums in sums_by_currency.items():
        currency_averages: list[int] = []
        for total, count in zip(sums, counts, strict=True):
            if total == 0:
                currency_averages.append(0)
            elif count == 0:
                currency_averages.append(total)
            else:
                currency_averages.append(total // count)
        averages[currency] = currency_averages
    return averages


def most_expensive_weekday(averages: list[int]) -> tuple[int | None, int]:
    best_index: int | None = None
    best_value = 0
    for index, value in enumerate(averages):
        if value > best_value:
            best_value = value
            best_index = index
    if best_index is None:
        return None, 0
    return best_index, best_value


def elapsed_days_in_period(date_from: datetime, date_to: datetime, now: datetime) -> int:
    effective_end = min(date_to.date(), tashkent_today(now))
    if effective_end < date_from.date():
        return 1
    return (effective_end - date_from.date()).days + 1


def ensure_currency_day_buckets(
    buckets: dict[str, list[int]], currency: str
) -> list[int]:
    if currency not in buckets:
        buckets[currency] = [0, 0, 0, 0, 0, 0, 0]
    return buckets[currency]


def month_start(year: int, month: int) -> datetime:
    return datetime(year, month, 1, tzinfo=UTC)


def last_twelve_months(now: datetime | None = None) -> list[tuple[int, int]]:
    now = now or datetime.now(UTC)
    year, month = now.year, now.month
    months: list[tuple[int, int]] = []
    for _ in range(12):
        months.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    months.reverse()
    return months


async def get_history(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    viewer: User,
    date_from: datetime,
    date_to: datetime,
    limit: int,
    offset: int,
    include_created_by: bool,
    expense_category_id: uuid.UUID | None = None,
) -> tuple[list[HistoryItem], int]:
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to")

    base_filters: tuple = (
        Transaction.family_budget_id == family_budget_id,
        Transaction.is_deleted.is_(False),
        Transaction.transaction_date >= date_from,
        Transaction.transaction_date <= date_to,
    )
    if expense_category_id is not None:
        base_filters = (
            *base_filters,
            Transaction.type == "expense",
            Transaction.expense_category_id == expense_category_id,
        )

    from_wallet = aliased(Wallet)
    to_wallet = aliased(Wallet)
    visibility = personal_ops_hidden_clause(viewer, from_wallet, to_wallet)

    count_stmt = (
        select(func.count())
        .select_from(Transaction)
        .join(from_wallet, Transaction.wallet_id == from_wallet.id)
        .outerjoin(to_wallet, Transaction.to_wallet_id == to_wallet.id)
        .where(*base_filters, visibility)
    )
    total_count = int(await session.scalar(count_stmt) or 0)
    expense_sub = aliased(ExpenseCategory)
    expense_parent = aliased(ExpenseCategory)
    income_cat = aliased(IncomeCategory)

    selected_columns = [
        Transaction,
        from_wallet.name.label("wallet_name"),
        from_wallet.translation_key.label("wallet_translation_key"),
        from_wallet.currency.label("currency"),
        to_wallet.name.label("to_wallet_name"),
        to_wallet.translation_key.label("to_wallet_translation_key"),
        to_wallet.currency.label("to_currency"),
        income_cat.name.label("income_category_name"),
        income_cat.translation_key.label("income_category_translation_key"),
        expense_parent.name.label("expense_category_name"),
        expense_parent.translation_key.label("expense_category_translation_key"),
        expense_sub.name.label("expense_subcategory_name"),
        expense_sub.translation_key.label("expense_subcategory_translation_key"),
    ]
    if include_created_by:
        selected_columns.extend(
            [
                User.id.label("user_id"),
                User.first_name.label("user_first_name"),
                User.username.label("user_username"),
                User.family_budget_id.label("user_family_budget_id"),
                User.is_deleted.label("user_is_deleted"),
            ]
        )

    stmt = (
        select(*selected_columns)
        .join(from_wallet, Transaction.wallet_id == from_wallet.id)
        .outerjoin(to_wallet, Transaction.to_wallet_id == to_wallet.id)
        .outerjoin(income_cat, Transaction.income_category_id == income_cat.id)
        .outerjoin(expense_sub, Transaction.expense_category_id == expense_sub.id)
        .outerjoin(expense_parent, expense_sub.parent_id == expense_parent.id)
        .where(*base_filters, visibility)
        .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if include_created_by:
        stmt = stmt.outerjoin(User, Transaction.created_by_user_id == User.id)

    rows = (await session.execute(stmt)).all()
    items: list[HistoryItem] = []
    for row in rows:
        txn: Transaction = row[0]
        created_by: str | None = None
        if include_created_by:
            author_user: User | None = None
            if row.user_id is not None:
                author_user = User(
                    id=row.user_id,
                    telegram_id=0,
                    family_budget_id=row.user_family_budget_id,
                    role="member",
                    language="ru",
                    first_name=row.user_first_name,
                    username=row.user_username,
                    is_deleted=row.user_is_deleted,
                )
            created_by = format_history_author(
                author_user, family_budget_id=family_budget_id
            )

        items.append(
            HistoryItem(
                id=txn.id,
                type=txn.type,
                transaction_date=txn.transaction_date,
                amount=txn.amount,
                currency=row.currency,
                wallet_id=txn.wallet_id,
                wallet_name=row.wallet_name,
                wallet_translation_key=row.wallet_translation_key,
                to_wallet_id=txn.to_wallet_id,
                to_wallet_name=row.to_wallet_name,
                to_wallet_translation_key=row.to_wallet_translation_key,
                to_amount=txn.to_amount,
                to_currency=row.to_currency,
                income_category_name=row.income_category_name,
                income_category_translation_key=row.income_category_translation_key,
                expense_category_name=row.expense_category_name,
                expense_category_translation_key=row.expense_category_translation_key,
                expense_subcategory_name=row.expense_subcategory_name,
                expense_subcategory_translation_key=row.expense_subcategory_translation_key,
                comment=txn.comment,
                created_by=created_by,
            )
        )

    return items, total_count


async def get_expenses_by_category(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    currency: str,
    date_from: datetime,
    date_to: datetime,
) -> list[CategoryAmount]:
    expense_sub = aliased(ExpenseCategory)
    expense_parent = aliased(ExpenseCategory)
    wallet = aliased(Wallet)

    stmt = (
        select(
            expense_parent.id.label("category_id"),
            expense_parent.name.label("category_name"),
            expense_parent.translation_key.label("category_translation_key"),
            expense_parent.color_index.label("color_index"),
            func.coalesce(func.sum(Transaction.amount), 0).label("amount"),
        )
        .join(wallet, Transaction.wallet_id == wallet.id)
        .join(expense_sub, Transaction.expense_category_id == expense_sub.id)
        .join(expense_parent, expense_sub.parent_id == expense_parent.id)
        .where(
            Transaction.family_budget_id == family_budget_id,
            Transaction.is_deleted.is_(False),
            Transaction.type == "expense",
            wallet.currency == currency,
            wallet.is_personal.is_(False),
            Transaction.transaction_date >= date_from,
            Transaction.transaction_date <= date_to,
        )
        .group_by(
            expense_parent.id,
            expense_parent.name,
            expense_parent.translation_key,
            expense_parent.color_index,
        )
        .order_by(func.sum(Transaction.amount).desc())
    )

    rows = (await session.execute(stmt)).all()
    return [
        CategoryAmount(
            category_id=row.category_id,
            category_name=row.category_name,
            category_translation_key=row.category_translation_key,
            color_index=row.color_index,
            amount=int(row.amount),
        )
        for row in rows
    ]


async def get_expenses_by_subcategory(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    parent_category_id: uuid.UUID,
    currency: str,
    date_from: datetime,
    date_to: datetime,
) -> list[SubcategoryAmount]:
    parent = await get_expense_parent_including_deleted(
        session, parent_category_id, family_budget_id
    )
    if parent is None or parent.parent_id is not None:
        raise HTTPException(status_code=404)

    expense_sub = aliased(ExpenseCategory)
    wallet = aliased(Wallet)

    stmt = (
        select(
            expense_sub.id.label("subcategory_id"),
            expense_sub.name.label("subcategory_name"),
            expense_sub.translation_key.label("subcategory_translation_key"),
            expense_sub.color_index.label("color_index"),
            func.coalesce(func.sum(Transaction.amount), 0).label("amount"),
        )
        .join(wallet, Transaction.wallet_id == wallet.id)
        .join(expense_sub, Transaction.expense_category_id == expense_sub.id)
        .where(
            Transaction.family_budget_id == family_budget_id,
            Transaction.is_deleted.is_(False),
            Transaction.type == "expense",
            wallet.currency == currency,
            wallet.is_personal.is_(False),
            expense_sub.parent_id == parent_category_id,
            Transaction.transaction_date >= date_from,
            Transaction.transaction_date <= date_to,
        )
        .group_by(
            expense_sub.id,
            expense_sub.name,
            expense_sub.translation_key,
            expense_sub.color_index,
        )
        .order_by(func.sum(Transaction.amount).desc())
    )

    rows = (await session.execute(stmt)).all()
    return [
        SubcategoryAmount(
            subcategory_id=row.subcategory_id,
            subcategory_name=row.subcategory_name,
            subcategory_translation_key=row.subcategory_translation_key,
            color_index=row.color_index,
            amount=int(row.amount),
        )
        for row in rows
    ]


async def get_income_by_category(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    currency: str,
    date_from: datetime,
    date_to: datetime,
) -> list[CategoryAmount]:
    wallet = aliased(Wallet)

    stmt = (
        select(
            IncomeCategory.id.label("category_id"),
            IncomeCategory.name.label("category_name"),
            IncomeCategory.translation_key.label("category_translation_key"),
            IncomeCategory.color_index.label("color_index"),
            func.coalesce(func.sum(Transaction.amount), 0).label("amount"),
        )
        .join(wallet, Transaction.wallet_id == wallet.id)
        .join(IncomeCategory, Transaction.income_category_id == IncomeCategory.id)
        .where(
            Transaction.family_budget_id == family_budget_id,
            Transaction.is_deleted.is_(False),
            Transaction.type == "income",
            wallet.currency == currency,
            wallet.is_personal.is_(False),
            Transaction.transaction_date >= date_from,
            Transaction.transaction_date <= date_to,
        )
        .group_by(
            IncomeCategory.id,
            IncomeCategory.name,
            IncomeCategory.translation_key,
            IncomeCategory.color_index,
        )
        .order_by(func.sum(Transaction.amount).desc())
    )

    rows = (await session.execute(stmt)).all()
    return [
        CategoryAmount(
            category_id=row.category_id,
            category_name=row.category_name,
            category_translation_key=row.category_translation_key,
            color_index=row.color_index,
            amount=int(row.amount),
        )
        for row in rows
    ]


async def get_trend(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    end: datetime | None = None,
) -> list[TrendEntry]:
    anchor = end or datetime.now(UTC)
    tashkent_anchor = anchor.astimezone(TASHKENT)
    months = last_twelve_months(
        datetime(tashkent_anchor.year, tashkent_anchor.month, 1, tzinfo=UTC)
    )
    month_keys = [f"{year:04d}-{month:02d}" for year, month in months]

    from_wallet = aliased(Wallet)
    month_bucket = func.date_trunc("month", Transaction.transaction_date)

    stmt = (
        select(
            month_bucket.label("month"),
            from_wallet.currency.label("currency"),
            Transaction.type.label("transaction_type"),
            func.sum(Transaction.amount).label("amount"),
        )
        .join(from_wallet, Transaction.wallet_id == from_wallet.id)
        .where(
            Transaction.family_budget_id == family_budget_id,
            Transaction.is_deleted.is_(False),
            Transaction.type.in_(("income", "expense")),
            from_wallet.is_personal.is_(False),
            Transaction.transaction_date >= month_start(*months[0]),
        )
        .group_by(month_bucket, from_wallet.currency, Transaction.type)
    )
    rows = (await session.execute(stmt)).all()

    totals: dict[tuple[str, str], dict[str, int]] = {}
    currencies: set[str] = set()

    for row in rows:
        currency: str = row.currency
        currencies.add(currency)
        key = f"{row.month.year:04d}-{row.month.month:02d}"
        bucket_key = (key, currency)
        if bucket_key not in totals:
            totals[bucket_key] = {"income": 0, "expense": 0}
        totals[bucket_key][row.transaction_type] = int(row.amount)

    entries: list[TrendEntry] = []
    for key in month_keys:
        for currency in sorted(currencies):
            data = totals.get((key, currency), {"income": 0, "expense": 0})
            entries.append(
                TrendEntry(
                    month=key,
                    currency=currency,
                    income=data["income"],
                    expense=data["expense"],
                )
            )

    return entries


async def get_summary(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    date_from: datetime,
    date_to: datetime,
    now: datetime | None = None,
) -> SummaryResponse:
    now = now or datetime.now(UTC)

    from_wallet = aliased(Wallet)
    to_wallet = aliased(Wallet)

    base_filters = (
        Transaction.family_budget_id == family_budget_id,
        Transaction.is_deleted.is_(False),
        Transaction.transaction_date >= date_from,
        Transaction.transaction_date <= date_to,
    )

    source_totals = (
        select(
            from_wallet.currency.label("currency"),
            func.sum(
                case((Transaction.type == "income", Transaction.amount), else_=0)
            ).label("income"),
            func.sum(
                case((Transaction.type == "expense", Transaction.amount), else_=0)
            ).label("expense"),
            func.sum(
                case(
                    (Transaction.type == "transfer", -Transaction.amount), else_=0
                )
            ).label("transfer_net"),
        )
        .join(from_wallet, Transaction.wallet_id == from_wallet.id)
        .where(*base_filters, from_wallet.is_personal.is_(False))
        .group_by(from_wallet.currency)
    )
    destination_totals = (
        select(
            to_wallet.currency.label("currency"),
            literal(0).label("income"),
            literal(0).label("expense"),
            func.sum(Transaction.to_amount).label("transfer_net"),
        )
        .join(to_wallet, Transaction.to_wallet_id == to_wallet.id)
        .where(
            *base_filters,
            Transaction.type == "transfer",
            Transaction.to_amount.is_not(None),
            to_wallet.is_personal.is_(False),
        )
        .group_by(to_wallet.currency)
    )
    totals_ledger = union_all(source_totals, destination_totals).subquery()
    totals_stmt = (
        select(
            totals_ledger.c.currency,
            func.sum(totals_ledger.c.income).label("income"),
            func.sum(totals_ledger.c.expense).label("expense"),
            func.sum(totals_ledger.c.transfer_net).label("transfer_net"),
        )
        .group_by(totals_ledger.c.currency)
    )
    total_rows = (await session.execute(totals_stmt)).all()

    isodow = func.extract(
        "isodow", func.timezone("UTC", Transaction.transaction_date)
    )
    weekday_stmt = (
        select(
            from_wallet.currency.label("currency"),
            isodow.label("isodow"),
            Transaction.type.label("transaction_type"),
            func.sum(Transaction.amount).label("amount"),
        )
        .join(from_wallet, Transaction.wallet_id == from_wallet.id)
        .where(
            *base_filters,
            Transaction.type.in_(("income", "expense")),
            from_wallet.is_personal.is_(False),
        )
        .group_by(from_wallet.currency, isodow, Transaction.type)
    )
    weekday_rows = (await session.execute(weekday_stmt)).all()

    currency_data = {
        row.currency: {
            "income": int(row.income),
            "expense": int(row.expense),
            "transfer_net": int(row.transfer_net),
        }
        for row in total_rows
    }
    day_of_week_expense_sums: dict[str, list[int]] = {}
    day_of_week_income: dict[str, list[int]] = {}

    for row in weekday_rows:
        buckets = (
            day_of_week_income
            if row.transaction_type == "income"
            else day_of_week_expense_sums
        )
        dow = ensure_currency_day_buckets(buckets, row.currency)
        dow[int(row.isodow) - 1] = int(row.amount)

    day_of_week_expense = expense_weekday_averages(
        day_of_week_expense_sums, date_from, date_to, now
    )

    elapsed = elapsed_days_in_period(date_from, date_to, now)
    by_currency: list[PerCurrencySummary] = []

    for currency in sorted(currency_data):
        data = currency_data[currency]
        income = int(data["income"])
        expense = int(data["expense"])
        transfer_net = int(data["transfer_net"])
        net_change = income - expense + transfer_net
        average_daily_expense = expense // elapsed if elapsed > 0 else 0
        expense_averages = day_of_week_expense.get(currency, [0, 0, 0, 0, 0, 0, 0])
        expensive_weekday, expensive_average = most_expensive_weekday(expense_averages)
        by_currency.append(
            PerCurrencySummary(
                currency=currency,
                income=income,
                expense=expense,
                transfer_net=transfer_net,
                net_change=net_change,
                average_daily_expense=average_daily_expense,
                most_expensive_weekday=expensive_weekday,
                most_expensive_weekday_average=expensive_average,
            )
        )

    return SummaryResponse(
        by_currency=by_currency,
        day_of_week_expense=day_of_week_expense,
        day_of_week_income=day_of_week_income,
    )


WALLET_BALANCE_CURRENCIES = ("UZS", "USD")


async def get_wallet_balances(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
) -> WalletBalancesResponse:
    from_wallet = aliased(Wallet)
    to_wallet = aliased(Wallet)

    source_ledger = (
        select(
            from_wallet.currency.label("currency"),
            case(
                (Transaction.type == "income", Transaction.amount),
                (Transaction.type == "expense", -Transaction.amount),
                (Transaction.type == "transfer", -Transaction.amount),
                else_=0,
            ).label("amount"),
        )
        .join(from_wallet, Transaction.wallet_id == from_wallet.id)
        .where(
            Transaction.family_budget_id == family_budget_id,
            Transaction.is_deleted.is_(False),
            from_wallet.is_personal.is_(False),
        )
    )
    destination_ledger = (
        select(
            to_wallet.currency.label("currency"),
            Transaction.to_amount.label("amount"),
        )
        .join(to_wallet, Transaction.to_wallet_id == to_wallet.id)
        .where(
            Transaction.family_budget_id == family_budget_id,
            Transaction.is_deleted.is_(False),
            Transaction.type == "transfer",
            Transaction.to_amount.is_not(None),
            to_wallet.is_personal.is_(False),
        )
    )
    ledger = union_all(source_ledger, destination_ledger).subquery()
    stmt = (
        select(
            ledger.c.currency,
            func.sum(ledger.c.amount).label("balance"),
        )
        .group_by(ledger.c.currency)
    )
    rows = (await session.execute(stmt)).all()
    balance_by_currency = {row.currency: int(row.balance) for row in rows}

    balances = [
        CurrencyBalance(
            currency=currency,
            balance=balance_by_currency.get(currency, 0),
        )
        for currency in WALLET_BALANCE_CURRENCIES
    ]

    return WalletBalancesResponse(balances=balances)


async def list_personal_wallet_currencies(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    viewer_id: uuid.UUID,
) -> list[str]:
    stmt = (
        select(Wallet.currency)
        .where(
            Wallet.family_budget_id == family_budget_id,
            Wallet.is_deleted.is_(False),
            Wallet.is_personal.is_(True),
            Wallet.owner_user_id == viewer_id,
        )
        .distinct()
        .order_by(Wallet.currency)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_personal_summary(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    viewer: User,
    date_from: datetime,
    date_to: datetime,
) -> PersonalSummaryResponse:
    currencies_with_wallets = await list_personal_wallet_currencies(
        session, family_budget_id, viewer.id
    )

    from_wallet = aliased(Wallet)

    base_filters = (
        Transaction.family_budget_id == family_budget_id,
        Transaction.is_deleted.is_(False),
        Transaction.transaction_date >= date_from,
        Transaction.transaction_date <= date_to,
    )

    totals_stmt = (
        select(
            from_wallet.currency.label("currency"),
            func.sum(
                case((Transaction.type == "income", Transaction.amount), else_=0)
            ).label("income"),
            func.sum(
                case((Transaction.type == "expense", Transaction.amount), else_=0)
            ).label("expense"),
        )
        .join(from_wallet, Transaction.wallet_id == from_wallet.id)
        .where(
            *base_filters,
            from_wallet.is_personal.is_(True),
            from_wallet.owner_user_id == viewer.id,
        )
        .group_by(from_wallet.currency)
    )
    total_rows = (await session.execute(totals_stmt)).all()
    currency_data = {
        row.currency: {"income": int(row.income), "expense": int(row.expense)}
        for row in total_rows
    }

    by_currency = [
        PersonalPerCurrencySummary(
            currency=currency,
            income=currency_data.get(currency, {}).get("income", 0),
            expense=currency_data.get(currency, {}).get("expense", 0),
        )
        for currency in currencies_with_wallets
    ]

    return PersonalSummaryResponse(
        currencies_with_wallets=currencies_with_wallets,
        by_currency=by_currency,
    )


async def get_personal_wallet_balances(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    viewer: User,
) -> PersonalWalletBalancesResponse:
    currencies_with_wallets = await list_personal_wallet_currencies(
        session, family_budget_id, viewer.id
    )

    from_wallet = aliased(Wallet)
    to_wallet = aliased(Wallet)

    source_ledger = (
        select(
            from_wallet.currency.label("currency"),
            case(
                (Transaction.type == "income", Transaction.amount),
                (Transaction.type == "expense", -Transaction.amount),
                (Transaction.type == "transfer", -Transaction.amount),
                else_=0,
            ).label("amount"),
        )
        .join(from_wallet, Transaction.wallet_id == from_wallet.id)
        .where(
            Transaction.family_budget_id == family_budget_id,
            Transaction.is_deleted.is_(False),
            from_wallet.is_personal.is_(True),
            from_wallet.owner_user_id == viewer.id,
        )
    )
    destination_ledger = (
        select(
            to_wallet.currency.label("currency"),
            Transaction.to_amount.label("amount"),
        )
        .join(to_wallet, Transaction.to_wallet_id == to_wallet.id)
        .where(
            Transaction.family_budget_id == family_budget_id,
            Transaction.is_deleted.is_(False),
            Transaction.type == "transfer",
            Transaction.to_amount.is_not(None),
            to_wallet.is_personal.is_(True),
            to_wallet.owner_user_id == viewer.id,
        )
    )
    ledger = union_all(source_ledger, destination_ledger).subquery()
    stmt = select(
        ledger.c.currency,
        func.sum(ledger.c.amount).label("balance"),
    ).group_by(ledger.c.currency)
    rows = (await session.execute(stmt)).all()
    balance_by_currency = {row.currency: int(row.balance) for row in rows}

    balances = [
        CurrencyBalance(
            currency=currency,
            balance=balance_by_currency.get(currency, 0),
        )
        for currency in WALLET_BALANCE_CURRENCIES
    ]

    return PersonalWalletBalancesResponse(
        currencies_with_wallets=currencies_with_wallets,
        balances=balances,
    )
