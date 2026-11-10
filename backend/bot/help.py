"""/help, /menu and any unknown /command: one hint with an open-app button (ux-fix B16).

This router must be included LAST so real commands are matched first.
"""

from aiogram import Bot, F, Router
from aiogram.types import BotCommand, Message
from sqlalchemy import select

from app.db import async_session_factory
from app.models.user import User
from app.services.bot_texts import SUPPORTED, t
from bot.onboarding import greeting_inline_keyboard

router = Router()

MENU_COMMANDS = ("start", "help")


@router.message(F.text.startswith("/"))
async def help_handler(message: Message) -> None:
    if message.from_user is None:
        return
    language = "ru"
    async with async_session_factory() as session:
        user = await session.scalar(
            select(User).where(
                User.telegram_id == message.from_user.id, User.is_deleted.is_(False)
            )
        )
        if user is not None:
            language = user.language
    await message.answer(
        t(language, "help.hint"), reply_markup=greeting_inline_keyboard(language)
    )


async def register_bot_commands(bot: Bot) -> None:
    """Command menu: default (RU) plus UZ for users whose Telegram language is uz."""
    for language in SUPPORTED:
        commands = [
            BotCommand(command=name, description=t(language, f"command.{name}"))
            for name in MENU_COMMANDS
        ]
        await bot.set_my_commands(
            commands, language_code=None if language == "ru" else language
        )
