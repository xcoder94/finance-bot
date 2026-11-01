"""Telegram hint sent right after the app starts waiting for a photo/voice sum."""

import logging

from app.models.user import User
from app.services.goal_notify import resolve_bot
from bot.quick_entry.pending_texts import cancel_keyboard, pending_hint_text

logger = logging.getLogger(__name__)


async def send_pending_hint(user: User, db_method: str, purchase_id: object = None) -> None:
    """Best effort: a Telegram failure must not fail the purchase request."""
    bot = None
    owned = False
    try:
        bot, owned = await resolve_bot(None)
        markup = cancel_keyboard(user.language, purchase_id) if purchase_id is not None else None
        await bot.send_message(
            user.telegram_id, pending_hint_text(user.language, db_method), reply_markup=markup
        )
    except Exception:
        logger.exception("Failed to send the pending-sum hint telegram_user_id=%s", user.telegram_id)
    finally:
        if owned and bot is not None:
            await bot.session.close()
