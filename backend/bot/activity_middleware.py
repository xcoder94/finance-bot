"""Outer middleware: any update from a user marks the user active in the bot today."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Dispatcher
from aiogram.types import TelegramObject

from app.services.activity import touch_activity

logger = logging.getLogger(__name__)


class ActivityMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        finally:
            # After the handler: /start creates the user inside it. Never raises.
            from_user = data.get("event_from_user")
            if from_user is not None and not from_user.is_bot:
                await touch_activity(telegram_id=from_user.id, bot=True)


def register_activity_middleware(dp: Dispatcher) -> None:
    dp.update.outer_middleware(ActivityMiddleware())
