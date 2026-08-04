import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import BOT_TOKEN, receipt_photo_enabled
from app.services.invite import cache_bot_username
from app.services.notification_scheduler import notification_loop
from bot.onboarding import router as onboarding_router
from bot.membership import router as membership_router
from bot.goals import router as goals_router
from bot.quick_entry.handlers import router as quick_entry_router

logging.basicConfig(level=logging.INFO)


def register_bot_routers(dp: Dispatcher) -> None:
    dp.include_router(onboarding_router)
    dp.include_router(membership_router)
    dp.include_router(goals_router)
    dp.include_router(quick_entry_router)
    if receipt_photo_enabled():
        from bot.quick_entry.receipt_photo import router as receipt_photo_router

        dp.include_router(receipt_photo_router)


async def _run_notification_loop(bot: Bot) -> None:
    await notification_loop(bot)


async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.startup.register(cache_bot_username)
    register_bot_routers(dp)
    loop_task = asyncio.create_task(_run_notification_loop(bot))
    try:
        await dp.start_polling(bot)
    finally:
        loop_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
