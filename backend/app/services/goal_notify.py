import uuid

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import BOT_TOKEN
from app.models.goal import Goal
from app.models.user import User
from app.services.bot_texts import t
from bot.quick_entry.cards import format_amount, format_number


def format_achievement_message(
    name: str, balance: int, target: int, currency: str, language: str | None = None
) -> str:
    return t(
        language,
        "goal.achieved",
        name=name,
        balance=format_amount(balance, currency, language),
        target=format_number(target),
    )


def owner_close_keyboard(
    goal_id: uuid.UUID, language: str | None = None
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(language, "goal.close"),
                    callback_data=f"goal:close:{goal_id}",
                )
            ]
        ]
    )


async def fan_out_achievement(
    session: AsyncSession,
    goal: Goal,
    balance: int,
    bot: Bot,
) -> None:
    stmt = select(User).where(
        User.family_budget_id == goal.family_budget_id,
        User.is_deleted.is_(False),
    )
    users = (await session.scalars(stmt)).all()
    for user in users:
        text = format_achievement_message(
            goal.name, balance, goal.target_amount, goal.currency, user.language
        )
        reply_markup = (
            owner_close_keyboard(goal.id, user.language)
            if user.role == "owner"
            else None
        )
        await bot.send_message(
            user.telegram_id, text, reply_markup=reply_markup
        )


async def resolve_bot(bot: Bot | None) -> tuple[Bot, bool]:
    if bot is not None:
        return bot, False
    return Bot(token=BOT_TOKEN), True
