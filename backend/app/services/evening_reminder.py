from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family_budget import FamilyBudget
from app.models.transaction import Transaction
from app.models.user import User

TASHKENT = ZoneInfo("Asia/Tashkent")

EVENING_REMINDER_TEXT = (
    "Сегодня не было ни одной записи.\n"
    "Напишите трату одной строкой — например, `продукты 150 тысяч`"
)


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime(day.year, day.month, day.day, tzinfo=TASHKENT)
    end = start + timedelta(days=1)
    return start, end


async def family_had_activity_on(
    session: AsyncSession,
    family_budget_id,
    day: date,
) -> bool:
    start, end = _day_bounds(day)
    stmt = select(func.count()).select_from(Transaction).where(
        Transaction.family_budget_id == family_budget_id,
        Transaction.is_deleted.is_(False),
        Transaction.transaction_date >= start,
        Transaction.transaction_date < end,
    )
    count = await session.scalar(stmt)
    return count > 0


async def send_evening_reminders_for_family(
    session: AsyncSession,
    budget: FamilyBudget,
    day: date,
    bot: Bot,
) -> int:
    stmt = select(User).where(
        User.family_budget_id == budget.id,
        User.is_deleted.is_(False),
        User.evening_reminder_enabled.is_(True),
    )
    users = (await session.scalars(stmt)).all()
    sent = 0
    for user in users:
        await bot.send_message(
            user.telegram_id,
            EVENING_REMINDER_TEXT,
            parse_mode="Markdown",
        )
        sent += 1
    return sent
