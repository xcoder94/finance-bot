import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent, Update

from app.config import BOT_TOKEN, receipt_photo_enabled, SUPPORT_CHAT_ID
from app.logging_setup import setup_logging
from app.services.invite import cache_bot_username
from app.services.notification_scheduler import notification_loop
from bot.keyboard_hygiene import ClearStaleReplyKeyboardMiddleware
from bot.onboarding import router as onboarding_router
from bot.membership import router as membership_router
from bot.goals import router as goals_router
from bot.support import router as support_router
from bot.quick_entry.handlers import router as quick_entry_router

setup_logging()
logger = logging.getLogger(__name__)


def _telegram_user_id_from_update(update: Update) -> int | None:
    if update.message and update.message.from_user:
        return update.message.from_user.id
    if update.callback_query and update.callback_query.from_user:
        return update.callback_query.from_user.id
    if update.edited_message and update.edited_message.from_user:
        return update.edited_message.from_user.id
    return None


def register_global_error_handler(dp: Dispatcher) -> None:
    @dp.errors()
    async def on_bot_error(event: ErrorEvent) -> bool:
        user_id = _telegram_user_id_from_update(event.update)
        # ErrorEvent carries the exception after aiogram already caught it —
        # logger.exception() would see empty sys.exc_info(); pass exc_info=.
        logger.error(
            "Unhandled bot update error telegram_user_id=%s update_id=%s: %s",
            user_id,
            event.update.update_id,
            event.exception,
            exc_info=event.exception,
        )
        return True


def register_bot_routers(dp: Dispatcher) -> None:
    dp.include_router(onboarding_router)
    dp.include_router(membership_router)
    dp.include_router(goals_router)
    if SUPPORT_CHAT_ID:
        dp.include_router(support_router)
    dp.include_router(quick_entry_router)
    if receipt_photo_enabled():
        from bot.quick_entry.receipt_photo import router as receipt_photo_router

        dp.include_router(receipt_photo_router)


async def _run_notification_loop(bot: Bot) -> None:
    await notification_loop(bot)


async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    bot.session.middleware(ClearStaleReplyKeyboardMiddleware())
    dp = Dispatcher(storage=MemoryStorage())
    register_global_error_handler(dp)
    dp.startup.register(cache_bot_username)
    register_bot_routers(dp)
    loop_task = asyncio.create_task(_run_notification_loop(bot))
    try:
        await dp.start_polling(bot)
    finally:
        loop_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
