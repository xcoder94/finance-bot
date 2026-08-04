import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import BOT_TOKEN
from app.services.invite import cache_bot_username
from bot.onboarding import router as onboarding_router
from bot.membership import router as membership_router
from bot.goals import router as goals_router
from bot.quick_entry.handlers import router as quick_entry_router

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.startup.register(cache_bot_username)
    dp.include_router(onboarding_router)
    dp.include_router(membership_router)
    dp.include_router(goals_router)
    dp.include_router(quick_entry_router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
