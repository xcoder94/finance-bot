import socket
import uuid
from datetime import date, datetime, timedelta
from unittest.mock import ANY, AsyncMock
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from app.models.goal import Goal
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.weekly_digest import (
    DIGEST_TITLE,
    SHOPPING_LEISURE_NAME,
    build_digest_body,
    build_owner_trailing_lines,
    digest_week_bounds,
    format_currency_block,
    format_goal_line,
    format_owner_trailing,
    goal_set_aside_this_week,
    send_weekly_digest_for_family,
)
from bot.quick_entry.cards import format_amount, format_number
from tests.test_wallets_categories import api_client, create_user_with_budget

TASHKENT = ZoneInfo("Asia/Tashkent")
MONDAY = date(2026, 8, 4)


def _db_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            return True
    except OSError:
        return False


def _tid() -> int:
    return int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000


def _ts(d: date, hour: int = 12) -> datetime:
    return datetime(d.year, d.month, d.day, hour, 0, tzinfo=TASHKENT)


def _inclusive_end(exclusive_end: datetime) -> datetime:
    return exclusive_end - timedelta(microseconds=1)


async def _add_parent_sub(
    session: AsyncSession,
    budget_id: uuid.UUID,
    parent_name: str,
    sub_name: str,
    *,
    translation_key: str | None = None,
) -> tuple[ExpenseCategory, ExpenseCategory]:
    parent = ExpenseCategory(
        family_budget_id=budget_id,
        name=parent_name,
        translation_key=translation_key,
    )
    session.add(parent)
    await session.flush()
    sub = ExpenseCategory(
        family_budget_id=budget_id,
        name=sub_name,
        parent_id=parent.id,
    )
    session.add(sub)
    await session.flush()
    return parent, sub


async def _expense(
    session: AsyncSession,
    *,
    budget_id: uuid.UUID,
    wallet_id: uuid.UUID,
    category_id: uuid.UUID,
    amount: int,
    user_id: uuid.UUID,
    txn_date: datetime,
) -> None:
    session.add(
        Transaction(
            family_budget_id=budget_id,
            type="expense",
            wallet_id=wallet_id,
            amount=amount,
            expense_category_id=category_id,
            created_by_user_id=user_id,
            transaction_date=txn_date,
        )
    )


def test_digest_week_bounds() -> None:
    this_start, this_end, last_start, last_end = digest_week_bounds(MONDAY)
    assert this_end == datetime(2026, 8, 4, 0, 0, tzinfo=TASHKENT)
    assert this_start == datetime(2026, 7, 28, 0, 0, tzinfo=TASHKENT)
    assert last_end == this_start
    assert last_start == datetime(2026, 7, 21, 0, 0, tzinfo=TASHKENT)


def test_format_currency_block_more_and_less() -> None:
    block = format_currency_block(
        currency="UZS",
        total=2_350_000,
        last_total=2_050_000,
        leader_name="Еда",
        leader_amount=940_000,
    )
    assert block == (
        f"Расходы: {format_amount(2_350_000, 'UZS')}\n"
        f"На {format_amount(300_000, 'UZS')} больше, чем на прошлой неделе\n"
        f"Больше всего — Еда, {format_amount(940_000, 'UZS')}"
    )
    block_less = format_currency_block(
        currency="USD",
        total=80,
        last_total=120,
        leader_name="Дом",
        leader_amount=90,
    )
    assert "меньше" in block_less
    assert format_amount(40, "USD") in block_less


def test_format_currency_block_omits_comparison_when_last_zero_or_delta_zero() -> None:
    no_last = format_currency_block(
        currency="USD",
        total=120,
        last_total=0,
        leader_name="Дом",
        leader_amount=90,
    )
    assert "прошлой неделе" not in no_last
    no_delta = format_currency_block(
        currency="UZS",
        total=500_000,
        last_total=500_000,
        leader_name="Еда",
        leader_amount=500_000,
    )
    assert "прошлой неделе" not in no_delta


def test_format_goal_line() -> None:
    line = format_goal_line(
        name="Ремонт",
        set_aside=500_000,
        balance=3_500_000,
        target=8_000_000,
        currency="UZS",
    )
    assert line == (
        f"Цель «Ремонт»: отложили {format_amount(500_000, 'UZS')}, "
        f"накоплено {format_amount(3_500_000, 'UZS')} из {format_number(8_000_000)}"
    )


def test_format_owner_trailing() -> None:
    assert format_owner_trailing("Ремонт") == (
        "Цель «Ремонт» достигнута — можно закрыть в разделе «Цели»"
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_build_digest_two_currencies_uzs_first(
    api_client: tuple[object, AsyncSession],
) -> None:
    _, session = api_client
    owner_tid = _tid()
    owner, budget = await create_user_with_budget(
        session, telegram_id=owner_tid, role="owner"
    )
    uzs_wallet = Wallet(family_budget_id=budget.id, name="UZS", currency="UZS")
    usd_wallet = Wallet(family_budget_id=budget.id, name="USD", currency="USD")
    session.add_all([uzs_wallet, usd_wallet])
    await session.flush()

    food_uzs, sub_food_uzs = await _add_parent_sub(session, budget.id, "Еда", "Продукты")
    transport_uzs, sub_transport_uzs = await _add_parent_sub(
        session, budget.id, "Транспорт", "Такси"
    )
    food_usd, sub_food_usd = await _add_parent_sub(session, budget.id, "Еда USD", "Продукты USD")
    transport_usd, sub_transport_usd = await _add_parent_sub(
        session, budget.id, "Дом", "Ремонт дома"
    )

    this_wed = date(2026, 7, 30)
    last_wed = date(2026, 7, 23)

    await _expense(
        session,
        budget_id=budget.id,
        wallet_id=uzs_wallet.id,
        category_id=sub_food_uzs.id,
        amount=500_000,
        user_id=owner.id,
        txn_date=_ts(this_wed),
    )
    await _expense(
        session,
        budget_id=budget.id,
        wallet_id=uzs_wallet.id,
        category_id=sub_transport_uzs.id,
        amount=300_000,
        user_id=owner.id,
        txn_date=_ts(this_wed),
    )
    await _expense(
        session,
        budget_id=budget.id,
        wallet_id=uzs_wallet.id,
        category_id=sub_food_uzs.id,
        amount=600_000,
        user_id=owner.id,
        txn_date=_ts(last_wed),
    )

    await _expense(
        session,
        budget_id=budget.id,
        wallet_id=usd_wallet.id,
        category_id=sub_food_usd.id,
        amount=100,
        user_id=owner.id,
        txn_date=_ts(this_wed),
    )
    await _expense(
        session,
        budget_id=budget.id,
        wallet_id=usd_wallet.id,
        category_id=sub_transport_usd.id,
        amount=50,
        user_id=owner.id,
        txn_date=_ts(this_wed),
    )
    await _expense(
        session,
        budget_id=budget.id,
        wallet_id=usd_wallet.id,
        category_id=sub_food_usd.id,
        amount=200,
        user_id=owner.id,
        txn_date=_ts(last_wed),
    )
    await session.flush()

    body = await build_digest_body(session, budget.id, MONDAY)
    lines = body.split("\n")
    assert lines[0] == DIGEST_TITLE
    uzs_idx = next(i for i, line in enumerate(lines) if line.startswith("Расходы:") and "сум" in line)
    usd_idx = next(i for i, line in enumerate(lines) if line.startswith("Расходы:") and "$" in line)
    assert uzs_idx < usd_idx
    assert format_amount(800_000, "UZS") in body
    assert "больше" in body
    assert "Еда" in body
    assert format_amount(500_000, "UZS") in body
    assert format_amount(150, "USD") in body
    assert "меньше" in body
    assert "Еда USD" in body
    assert format_amount(100, "USD") in body


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_usd_block_without_comparison_when_last_week_empty(
    api_client: tuple[object, AsyncSession],
) -> None:
    _, session = api_client
    owner, budget = await create_user_with_budget(session, telegram_id=_tid(), role="owner")
    usd_wallet = Wallet(family_budget_id=budget.id, name="USD", currency="USD")
    session.add(usd_wallet)
    await session.flush()
    _, sub = await _add_parent_sub(session, budget.id, "Дом", "Мебель")
    await _expense(
        session,
        budget_id=budget.id,
        wallet_id=usd_wallet.id,
        category_id=sub.id,
        amount=90,
        user_id=owner.id,
        txn_date=_ts(date(2026, 8, 1)),
    )
    await session.flush()

    body = await build_digest_body(session, budget.id, MONDAY)
    assert format_amount(90, "USD") in body
    assert "прошлой неделе" not in body


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_shopping_leisure_shows_subcategory_leader(
    api_client: tuple[object, AsyncSession],
) -> None:
    _, session = api_client
    owner, budget = await create_user_with_budget(session, telegram_id=_tid(), role="owner")
    wallet = Wallet(family_budget_id=budget.id, name="UZS", currency="UZS")
    session.add(wallet)
    await session.flush()
    parent = ExpenseCategory(
        family_budget_id=budget.id,
        name=SHOPPING_LEISURE_NAME,
        translation_key="shopping_leisure",
    )
    session.add(parent)
    await session.flush()
    sub_clothes = ExpenseCategory(
        family_budget_id=budget.id, name="Одежда", parent_id=parent.id
    )
    sub_fun = ExpenseCategory(
        family_budget_id=budget.id, name="Развлечения", parent_id=parent.id
    )
    session.add_all([sub_clothes, sub_fun])
    await session.flush()
    _, sub_food = await _add_parent_sub(session, budget.id, "Еда", "Продукты")
    await _expense(
        session,
        budget_id=budget.id,
        wallet_id=wallet.id,
        category_id=sub_clothes.id,
        amount=400_000,
        user_id=owner.id,
        txn_date=_ts(date(2026, 7, 29)),
    )
    await _expense(
        session,
        budget_id=budget.id,
        wallet_id=wallet.id,
        category_id=sub_fun.id,
        amount=100_000,
        user_id=owner.id,
        txn_date=_ts(date(2026, 7, 29)),
    )
    await _expense(
        session,
        budget_id=budget.id,
        wallet_id=wallet.id,
        category_id=sub_food.id,
        amount=200_000,
        user_id=owner.id,
        txn_date=_ts(date(2026, 7, 29)),
    )
    await session.flush()

    body = await build_digest_body(session, budget.id, MONDAY)
    assert "Больше всего — Одежда," in body
    assert SHOPPING_LEISURE_NAME not in body.split("Больше всего")[1].split("\n")[0]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_income_not_in_digest(
    api_client: tuple[object, AsyncSession],
) -> None:
    _, session = api_client
    owner, budget = await create_user_with_budget(session, telegram_id=_tid(), role="owner")
    wallet = Wallet(family_budget_id=budget.id, name="UZS", currency="UZS")
    income_cat = IncomeCategory(family_budget_id=budget.id, name="Зарплата")
    session.add_all([wallet, income_cat])
    await session.flush()
    _, sub = await _add_parent_sub(session, budget.id, "Еда", "Продукты")
    await _expense(
        session,
        budget_id=budget.id,
        wallet_id=wallet.id,
        category_id=sub.id,
        amount=50_000,
        user_id=owner.id,
        txn_date=_ts(date(2026, 7, 30)),
    )
    session.add(
        Transaction(
            family_budget_id=budget.id,
            type="income",
            wallet_id=wallet.id,
            amount=10_000_000,
            income_category_id=income_cat.id,
            created_by_user_id=owner.id,
            transaction_date=_ts(date(2026, 7, 30)),
        )
    )
    await session.flush()

    body = await build_digest_body(session, budget.id, MONDAY)
    assert "10 000 000" not in body
    assert format_amount(50_000, "UZS") in body


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_personal_expense_excluded_from_digest(
    api_client: tuple[object, AsyncSession],
) -> None:
    _, session = api_client
    owner, budget = await create_user_with_budget(session, telegram_id=_tid(), role="owner")
    shared = Wallet(family_budget_id=budget.id, name="Shared", currency="UZS")
    personal = Wallet(
        family_budget_id=budget.id,
        name="Personal",
        currency="UZS",
        is_personal=True,
        owner_user_id=owner.id,
    )
    session.add_all([shared, personal])
    await session.flush()
    _, sub = await _add_parent_sub(session, budget.id, "Еда", "Продукты")
    await _expense(
        session,
        budget_id=budget.id,
        wallet_id=shared.id,
        category_id=sub.id,
        amount=100_000,
        user_id=owner.id,
        txn_date=_ts(date(2026, 7, 30)),
    )
    await _expense(
        session,
        budget_id=budget.id,
        wallet_id=personal.id,
        category_id=sub.id,
        amount=9_000_000,
        user_id=owner.id,
        txn_date=_ts(date(2026, 7, 30)),
    )
    await session.flush()

    body = await build_digest_body(session, budget.id, MONDAY)
    assert format_amount(100_000, "UZS") in body
    assert "9 000 000" not in body


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_goal_line_when_set_aside_positive(
    api_client: tuple[object, AsyncSession],
) -> None:
    _, session = api_client
    owner, budget = await create_user_with_budget(session, telegram_id=_tid(), role="owner")
    source = Wallet(family_budget_id=budget.id, name="Cash", currency="UZS")
    goal_wallet = Wallet(family_budget_id=budget.id, name="Goal", currency="UZS")
    session.add_all([source, goal_wallet])
    await session.flush()
    goal = Goal(
        family_budget_id=budget.id,
        wallet_id=goal_wallet.id,
        name="Ремонт",
        target_amount=8_000_000,
        currency="UZS",
        status="active",
        crossed=False,
    )
    session.add(goal)
    _, sub = await _add_parent_sub(session, budget.id, "Еда", "Продукты")
    await _expense(
        session,
        budget_id=budget.id,
        wallet_id=source.id,
        category_id=sub.id,
        amount=100_000,
        user_id=owner.id,
        txn_date=_ts(date(2026, 7, 30)),
    )
    session.add(
        Transaction(
            family_budget_id=budget.id,
            type="transfer",
            wallet_id=source.id,
            to_wallet_id=goal_wallet.id,
            amount=500_000,
            to_amount=500_000,
            created_by_user_id=owner.id,
            transaction_date=_ts(date(2026, 7, 31)),
        )
    )
    await session.flush()

    body = await build_digest_body(session, budget.id, MONDAY)
    assert "отложили" in body
    assert format_amount(500_000, "UZS") in body
    assert "Ремонт" in body

    this_start, this_end, _, _ = digest_week_bounds(MONDAY)
    assert (
        await goal_set_aside_this_week(session, goal, this_start, this_end) == 500_000
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_goal_line_omitted_when_zero_set_aside(
    api_client: tuple[object, AsyncSession],
) -> None:
    _, session = api_client
    owner, budget = await create_user_with_budget(session, telegram_id=_tid(), role="owner")
    wallet = Wallet(family_budget_id=budget.id, name="Cash", currency="UZS")
    goal_wallet = Wallet(family_budget_id=budget.id, name="Goal", currency="UZS")
    session.add_all([wallet, goal_wallet])
    await session.flush()
    session.add(
        Goal(
            family_budget_id=budget.id,
            wallet_id=goal_wallet.id,
            name="Ремонт",
            target_amount=8_000_000,
            currency="UZS",
            status="active",
            crossed=False,
        )
    )
    _, sub = await _add_parent_sub(session, budget.id, "Еда", "Продукты")
    await _expense(
        session,
        budget_id=budget.id,
        wallet_id=wallet.id,
        category_id=sub.id,
        amount=100_000,
        user_id=owner.id,
        txn_date=_ts(date(2026, 7, 30)),
    )
    await session.flush()

    body = await build_digest_body(session, budget.id, MONDAY)
    assert "отложили" not in body
    assert "Цель" not in body


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_owner_trailing_only_for_owner_send(
    api_client: tuple[object, AsyncSession],
) -> None:
    _, session = api_client
    owner_tid = _tid()
    member_tid = owner_tid + 1
    owner, budget = await create_user_with_budget(
        session, telegram_id=owner_tid, role="owner"
    )
    member = User(
        telegram_id=member_tid,
        family_budget_id=budget.id,
        role="member",
        language="ru",
    )
    session.add(member)
    wallet = Wallet(family_budget_id=budget.id, name="Cash", currency="UZS")
    goal_wallet = Wallet(family_budget_id=budget.id, name="Goal", currency="UZS")
    session.add_all([wallet, goal_wallet])
    await session.flush()
    session.add(
        Goal(
            family_budget_id=budget.id,
            wallet_id=goal_wallet.id,
            name="Ремонт",
            target_amount=1_000_000,
            currency="UZS",
            status="active",
            crossed=True,
        )
    )
    _, sub = await _add_parent_sub(session, budget.id, "Еда", "Продукты")
    await _expense(
        session,
        budget_id=budget.id,
        wallet_id=wallet.id,
        category_id=sub.id,
        amount=50_000,
        user_id=owner.id,
        txn_date=_ts(date(2026, 7, 30)),
    )
    await session.flush()

    body = await build_digest_body(session, budget.id, MONDAY)
    trailing = await build_owner_trailing_lines(session, budget.id)
    assert trailing == [format_owner_trailing("Ремонт")]
    assert "достигнута" not in body

    bot = AsyncMock()
    count = await send_weekly_digest_for_family(session, budget, MONDAY, bot)
    assert count == 2
    owner_text = bot.send_message.await_args_list[0].args[1]
    member_text = bot.send_message.await_args_list[1].args[1]
    if bot.send_message.await_args_list[0].args[0] == member.telegram_id:
        owner_text, member_text = member_text, owner_text
    assert "достигнута" in owner_text
    assert owner_text.startswith(body)
    assert "достигнута" not in member_text
    assert member_text == body


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_send_skips_user_with_weekly_digest_disabled(
    api_client: tuple[object, AsyncSession],
) -> None:
    _, session = api_client
    owner_tid = _tid()
    member_tid = owner_tid + 1
    owner, budget = await create_user_with_budget(
        session, telegram_id=owner_tid, role="owner"
    )
    owner.weekly_digest_enabled = False
    member = User(
        telegram_id=member_tid,
        family_budget_id=budget.id,
        role="member",
        language="ru",
        weekly_digest_enabled=True,
    )
    session.add(member)
    wallet = Wallet(family_budget_id=budget.id, name="Cash", currency="UZS")
    session.add(wallet)
    await session.flush()
    _, sub = await _add_parent_sub(session, budget.id, "Еда", "Продукты")
    await _expense(
        session,
        budget_id=budget.id,
        wallet_id=wallet.id,
        category_id=sub.id,
        amount=50_000,
        user_id=owner.id,
        txn_date=_ts(date(2026, 7, 30)),
    )
    await session.flush()

    bot = AsyncMock()
    count = await send_weekly_digest_for_family(session, budget, MONDAY, bot)
    assert count == 1
    bot.send_message.assert_awaited_once_with(member.telegram_id, ANY)
