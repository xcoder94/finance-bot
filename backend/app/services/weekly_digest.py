from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family_budget import FamilyBudget
from app.models.goal import Goal
from app.models.transaction import Transaction
from app.models.user import User
from app.services.history_analytics import (
    get_expenses_by_category,
    get_expenses_by_subcategory,
)
from app.services.quick_entry_balance import wallet_balance
from bot.quick_entry.cards import format_amount, format_number

TASHKENT = ZoneInfo("Asia/Tashkent")

DIGEST_TITLE = "Итоги недели"
SHOPPING_LEISURE_NAME = "Покупки и досуг"


def digest_week_bounds(
    monday: date,
) -> tuple[datetime, datetime, datetime, datetime]:
    this_end = datetime(monday.year, monday.month, monday.day, tzinfo=TASHKENT)
    this_start = this_end - timedelta(days=7)
    last_end = this_start
    last_start = this_start - timedelta(days=7)
    return this_start, this_end, last_start, last_end


def _inclusive_end(exclusive_end: datetime) -> datetime:
    return exclusive_end - timedelta(microseconds=1)


def format_currency_block(
    *,
    currency: str,
    total: int,
    last_total: int,
    leader_name: str,
    leader_amount: int,
) -> str:
    lines = [f"Расходы: {format_amount(total, currency)}"]
    delta = total - last_total
    if last_total > 0 and delta != 0:
        direction = "больше" if delta > 0 else "меньше"
        lines.append(
            f"На {format_amount(abs(delta), currency)} {direction}, "
            "чем на прошлой неделе"
        )
    lines.append(
        f"Больше всего — {leader_name}, {format_amount(leader_amount, currency)}"
    )
    return "\n".join(lines)


def format_goal_line(
    *,
    name: str,
    set_aside: int,
    balance: int,
    target: int,
    currency: str,
) -> str:
    return (
        f"Цель «{name}»: отложили {format_amount(set_aside, currency)}, "
        f"накоплено {format_amount(balance, currency)} из {format_number(target)}"
    )


def format_owner_trailing(name: str) -> str:
    return f"Цель «{name}» достигнута — можно закрыть в разделе «Цели»"


async def goal_set_aside_this_week(
    session: AsyncSession,
    goal: Goal,
    start: datetime,
    end: datetime,
) -> int:
    transfer_in = case(
        (
            (Transaction.to_wallet_id == goal.wallet_id)
            & (Transaction.type == "transfer"),
            Transaction.to_amount,
        ),
        else_=0,
    )
    income_on = case(
        (
            (Transaction.wallet_id == goal.wallet_id)
            & (Transaction.type == "income"),
            Transaction.amount,
        ),
        else_=0,
    )
    stmt = select(
        func.coalesce(func.sum(transfer_in + income_on), 0)
    ).where(
        Transaction.family_budget_id == goal.family_budget_id,
        Transaction.is_deleted.is_(False),
        Transaction.transaction_date >= start,
        Transaction.transaction_date < end,
        or_(
            (Transaction.to_wallet_id == goal.wallet_id)
            & (Transaction.type == "transfer"),
            (Transaction.wallet_id == goal.wallet_id)
            & (Transaction.type == "income"),
        ),
    )
    return int(await session.scalar(stmt) or 0)


async def _currency_total(
    session: AsyncSession,
    family_budget_id,
    currency: str,
    date_from: datetime,
    date_to: datetime,
) -> int:
    cats = await get_expenses_by_category(
        session, family_budget_id, currency, date_from, date_to
    )
    return sum(cat.amount for cat in cats)


async def _leader_for_currency(
    session: AsyncSession,
    family_budget_id,
    currency: str,
    date_from: datetime,
    date_to: datetime,
) -> tuple[str, int] | None:
    cats = await get_expenses_by_category(
        session, family_budget_id, currency, date_from, date_to
    )
    if not cats:
        return None
    top = cats[0]
    leader_name = top.category_name
    leader_amount = top.amount
    if (
        top.category_name == SHOPPING_LEISURE_NAME
        or top.category_translation_key == "shopping_leisure"
    ):
        subs = await get_expenses_by_subcategory(
            session,
            family_budget_id,
            top.category_id,
            currency,
            date_from,
            date_to,
        )
        if subs:
            leader_name = subs[0].subcategory_name
            leader_amount = subs[0].amount
    return leader_name, leader_amount


async def _best_goal_line(
    session: AsyncSession,
    family_budget_id,
    this_start: datetime,
    this_end: datetime,
) -> str | None:
    stmt = select(Goal).where(
        Goal.family_budget_id == family_budget_id,
        Goal.status == "active",
    )
    goals = (await session.scalars(stmt)).all()
    best: Goal | None = None
    best_set_aside = 0
    for goal in goals:
        set_aside = await goal_set_aside_this_week(
            session, goal, this_start, this_end
        )
        if set_aside > best_set_aside:
            best_set_aside = set_aside
            best = goal
    if best is None or best_set_aside <= 0:
        return None
    balance = await wallet_balance(session, best.wallet_id)
    return format_goal_line(
        name=best.name,
        set_aside=best_set_aside,
        balance=balance,
        target=best.target_amount,
        currency=best.currency,
    )


async def build_digest_body(
    session: AsyncSession,
    family_budget_id,
    monday: date,
) -> str:
    this_start, this_end, last_start, last_end = digest_week_bounds(monday)
    this_to = _inclusive_end(this_end)
    last_to = _inclusive_end(last_end)

    parts: list[str] = [DIGEST_TITLE]
    currency_blocks: list[str] = []

    for currency in ("UZS", "USD"):
        total = await _currency_total(
            session, family_budget_id, currency, this_start, this_to
        )
        if total <= 0:
            continue
        last_total = await _currency_total(
            session, family_budget_id, currency, last_start, last_to
        )
        leader = await _leader_for_currency(
            session, family_budget_id, currency, this_start, this_to
        )
        if leader is None:
            continue
        leader_name, leader_amount = leader
        currency_blocks.append(
            format_currency_block(
                currency=currency,
                total=total,
                last_total=last_total,
                leader_name=leader_name,
                leader_amount=leader_amount,
            )
        )

    if currency_blocks:
        parts.append("\n\n".join(currency_blocks))

    goal_line = await _best_goal_line(session, family_budget_id, this_start, this_end)
    if goal_line is not None:
        if len(parts) > 1:
            parts.append("")
        parts.append(goal_line)

    return "\n".join(parts)


async def build_owner_trailing_lines(
    session: AsyncSession,
    family_budget_id,
) -> list[str]:
    stmt = (
        select(Goal)
        .where(
            Goal.family_budget_id == family_budget_id,
            Goal.status == "active",
            Goal.crossed.is_(True),
        )
        .order_by(Goal.name, Goal.created_at)
    )
    goals = (await session.scalars(stmt)).all()
    return [format_owner_trailing(goal.name) for goal in goals]


async def send_weekly_digest_for_family(
    session: AsyncSession,
    budget: FamilyBudget,
    monday: date,
    bot: Bot,
) -> int:
    body = await build_digest_body(session, budget.id, monday)
    trailing = await build_owner_trailing_lines(session, budget.id)

    stmt = select(User).where(
        User.family_budget_id == budget.id,
        User.is_deleted.is_(False),
        User.weekly_digest_enabled.is_(True),
    )
    users = (await session.scalars(stmt)).all()
    sent = 0
    for user in users:
        text = body
        if user.role == "owner" and trailing:
            text = body + "\n" + "\n".join(trailing)
        await bot.send_message(user.telegram_id, text)
        sent += 1
    return sent
