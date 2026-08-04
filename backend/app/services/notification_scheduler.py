import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_factory
from app.models.family_budget import FamilyBudget
from app.services.evening_reminder import (
    family_had_activity_on,
    send_evening_reminders_for_family,
)
from app.services.weekly_digest import send_weekly_digest_for_family

TASHKENT = ZoneInfo("Asia/Tashkent")

logger = logging.getLogger(__name__)


def is_evening_reminder_slot(now: datetime) -> bool:
    local = now.astimezone(TASHKENT)
    return local.hour == 21 and local.minute == 0


def is_weekly_digest_slot(now: datetime) -> bool:
    local = now.astimezone(TASHKENT)
    return local.weekday() == 0 and local.hour == 10 and local.minute == 0


async def tick(session: AsyncSession, now: datetime, bot: Bot) -> None:
    local = now.astimezone(TASHKENT)
    today = local.date()

    if is_evening_reminder_slot(now):
        stmt = select(FamilyBudget).where(FamilyBudget.is_deleted.is_(False))
        budgets = (await session.scalars(stmt)).all()
        for budget in budgets:
            if budget.last_evening_reminder_on == today:
                continue
            if not await family_had_activity_on(session, budget.id, today):
                await send_evening_reminders_for_family(session, budget, today, bot)
            budget.last_evening_reminder_on = today

    if is_weekly_digest_slot(now):
        stmt = select(FamilyBudget).where(FamilyBudget.is_deleted.is_(False))
        budgets = (await session.scalars(stmt)).all()
        for budget in budgets:
            if budget.last_weekly_digest_on == today:
                continue
            await send_weekly_digest_for_family(session, budget, today, bot)
            budget.last_weekly_digest_on = today


async def notification_loop(
    bot: Bot,
    *,
    sleep_seconds: float = 60.0,
    clock: Callable[[], datetime] = datetime.now,
) -> None:
    while True:
        try:
            now = clock()
            async with async_session_factory() as session:
                await tick(session, now, bot)
                await session.commit()
        except Exception:
            logger.exception("notification tick failed")
        await asyncio.sleep(sleep_seconds)
