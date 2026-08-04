import uuid

from aiogram import F, Router
from aiogram.types import CallbackQuery
from fastapi import HTTPException

from app.db import async_session_factory
from app.services.goals import close_goal
from bot.onboarding import get_active_user_by_telegram_id

router = Router()


@router.callback_query(F.data.startswith("goal:close:"))
async def handle_goal_close(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return

    raw_id = callback.data.split(":", 2)[2] if callback.data else ""
    try:
        goal_id = uuid.UUID(raw_id)
    except ValueError:
        await callback.answer()
        return

    async with async_session_factory() as session:
        user = await get_active_user_by_telegram_id(
            session, callback.from_user.id
        )
        if user is None or user.role != "owner":
            await callback.answer()
            return

        try:
            await close_goal(session, user, goal_id)
        except HTTPException:
            await callback.answer()
            return

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
