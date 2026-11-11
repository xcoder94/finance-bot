import logging
import uuid
from typing import Any

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


Outbox = list[tuple[int, str, InlineKeyboardMarkup | None]]


async def prepare_achievement(session: AsyncSession, goal: Goal, balance: int) -> Outbox:
    """Messages for every family member, built while the goal is still loaded (before commit)."""
    stmt = select(User).where(
        User.family_budget_id == goal.family_budget_id,
        User.is_deleted.is_(False),
    )
    users = (await session.scalars(stmt)).all()
    outbox: Outbox = []
    for user in users:
        text = format_achievement_message(
            goal.name, balance, goal.target_amount, goal.currency, user.language
        )
        reply_markup = (
            owner_close_keyboard(goal.id, user.language)
            if user.role == "owner"
            else None
        )
        outbox.append((user.telegram_id, text, reply_markup))
    return outbox


async def send_outbox(bot: Bot, outbox: Outbox) -> None:
    for chat_id, text, reply_markup in outbox:
        await send_notice_safe(bot, chat_id, text, reply_markup=reply_markup)


async def fan_out_achievement(
    session: AsyncSession,
    goal: Goal,
    balance: int,
    bot: Bot,
) -> None:
    await send_outbox(bot, await prepare_achievement(session, goal, balance))


class _InertBot:
    """Stand-in when the real Bot cannot be built (bad/missing token): every send fails safely."""

    class session:  # noqa: N801
        @staticmethod
        async def close() -> None:
            return None

    async def send_message(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError("telegram bot unavailable")


async def resolve_bot(bot: Bot | None) -> tuple[Bot, bool]:
    if bot is not None:
        return bot, False
    try:
        return Bot(token=BOT_TOKEN), True
    except Exception as exc:  # noqa: BLE001 - invalid token must not break a saved change
        logging.getLogger(__name__).warning(
            "telegram bot not created: %s", type(exc).__name__
        )
        return _InertBot(), False  # type: ignore[return-value]


async def send_notice_safe(bot: Bot, chat_id: int, text: str, **kwargs: Any) -> bool:
    """Best-effort Telegram notice: a delivery failure never breaks the caller's
    already-decided state change. The error is logged (type only, no text)."""
    try:
        await bot.send_message(chat_id, text, **kwargs)
    except Exception as exc:  # noqa: BLE001 - blocked bot, network, bad token...
        logging.getLogger(__name__).warning(
            "telegram notice to %s not delivered: %s", chat_id, type(exc).__name__
        )
        return False
    return True
