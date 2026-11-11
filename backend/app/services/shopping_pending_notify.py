"""Telegram hint sent right after the app starts waiting for a photo/voice sum."""

import logging

from app.models.user import User
from app.services.goal_notify import deliver, spawn_background
from bot.quick_entry.pending_texts import cancel_keyboard, pending_hint_text

logger = logging.getLogger(__name__)


async def send_pending_hint(user: User, db_method: str, purchase_id: object = None) -> None:
    """Best effort, in the background: the API answer never waits for Telegram."""
    try:
        markup = cancel_keyboard(user.language, purchase_id) if purchase_id is not None else None
        text = pending_hint_text(user.language, db_method)
        spawn_background(deliver(None, [(user.telegram_id, text, {"reply_markup": markup})]))
    except Exception:
        logger.exception("Failed to queue the pending-sum hint telegram_user_id=%s", user.telegram_id)
