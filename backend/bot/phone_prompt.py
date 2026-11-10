"""Phone-number request right after a NEW user's first /start (admin design section 5).

State lives in users.phone_prompted_at / phone_prompt_closed_at / phone / phone_shared_at.
The number is PII: it is never logged and never put into an exception message.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from aiogram import BaseMiddleware, F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    TelegramObject,
)
from sqlalchemy import update

from app.db import async_session_factory
from app.models.user import User
from app.services.bot_texts import CATALOGUE

logger = logging.getLogger(__name__)

router = Router(name="phone_prompt")

STRINGS: dict[str, dict[str, str]] = {
    key: CATALOGUE[f"phone.{key}"]
    for key in ("prompt", "share", "skip", "saved", "skipped", "restored", "foreign")
}

_SKIP_LABELS = frozenset(STRINGS["skip"].values())
_PHONE_RE = re.compile(r"^\+[0-9]{5,19}$")

# chat_id -> language: the prompt was closed by an ordinary message, so the next bot
# message to that chat must bring the ordinary keyboard back (see keyboard_hygiene).
pending_keyboard_restore: dict[int, str] = {}


def _s(key: str, language: str) -> str:
    return STRINGS[key]["uz" if language == "uz" else "ru"]


def prompt_text(language: str) -> str:
    return _s("prompt", language)


def prompt_keyboard(language: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=_s("share", language), request_contact=True)],
            [KeyboardButton(text=_s("skip", language))],
        ],
        resize_keyboard=True,
    )


def normalize_phone(raw: str | None) -> str | None:
    """'998901234567' / '+998 90 123-45-67' -> '+998901234567'; None if not 5-19 digits."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    phone = f"+{digits}"
    return phone if _PHONE_RE.match(phone) else None


def _now() -> datetime:
    return datetime.now(UTC)


async def _close_prompt(telegram_id: int, *, phone: str | None = None) -> str | None:
    """Close an OPEN prompt (optionally storing the phone). Returns the user's language if a
    prompt was open and is now closed, else None. One conditional UPDATE: race-safe."""
    now = _now()
    values: dict[str, Any] = {"phone_prompt_closed_at": now}
    if phone is not None:
        values.update(phone=phone, phone_shared_at=now)
    async with async_session_factory() as session:
        language = await session.scalar(
            update(User)
            .where(
                User.telegram_id == telegram_id,
                User.is_deleted.is_(False),
                User.phone_prompted_at.is_not(None),
                User.phone_prompt_closed_at.is_(None),
            )
            .values(**values)
            .returning(User.language)
        )
        await session.commit()
    return language


async def _user_language(telegram_id: int) -> str | None:
    """Language of an existing (not deleted) user; None for strangers."""
    from sqlalchemy import select

    async with async_session_factory() as session:
        return await session.scalar(
            select(User.language).where(User.telegram_id == telegram_id, User.is_deleted.is_(False))
        )


async def _save_phone(telegram_id: int, phone: str) -> None:
    """Store the phone of a user whose prompt is already closed (or was never opened)."""
    async with async_session_factory() as session:
        await session.execute(
            update(User)
            .where(User.telegram_id == telegram_id, User.is_deleted.is_(False))
            .values(phone=phone, phone_shared_at=_now())
        )
        await session.commit()


class PhonePromptMiddleware(BaseMiddleware):
    """Any message other than the two prompt answers closes an open prompt (= skipped)."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if (
            isinstance(event, Message)
            and event.from_user is not None
            and not event.from_user.is_bot
            and event.contact is None
            and (event.text or "") not in _SKIP_LABELS
        ):
            try:
                language = await _close_prompt(event.from_user.id)
            except Exception:
                logger.exception("phone prompt close failed telegram_id=%s", event.from_user.id)
                language = None
            if language is not None:
                pending_keyboard_restore[event.chat.id] = language
        try:
            return await handler(event, data)
        finally:
            await self._restore_keyboard_now(event)

    @staticmethod
    async def _restore_keyboard_now(event: TelegramObject) -> None:
        """The reply to the message that closed the prompt usually carries an inline card, which
        cannot replace the reply keyboard. If nobody has consumed the pending restore by now, send
        a short separate message that brings the ordinary keyboard back (card stays intact)."""
        if not isinstance(event, Message):
            return
        language = pending_keyboard_restore.pop(event.chat.id, None)
        if language is None:
            return
        try:
            await event.answer(_s("restored", language), reply_markup=_ordinary_keyboard(language))
        except Exception:
            logger.exception("keyboard restore failed chat_id=%s", event.chat.id)


router.message.outer_middleware(PhonePromptMiddleware())


def _ordinary_keyboard(language: str) -> Any:
    from bot.support import build_main_reply_keyboard

    return build_main_reply_keyboard(language)


@router.message(F.contact)
async def contact_handler(message: Message) -> None:
    if message.from_user is None or message.contact is None:
        return
    telegram_id = message.from_user.id
    language = await _user_language(telegram_id)
    if language is None:
        raise SkipHandler  # not our user
    contact = message.contact
    phone = normalize_phone(contact.phone_number) if contact.user_id == telegram_id else None
    if phone is None:
        await message.answer(_s("foreign", language), reply_markup=prompt_keyboard(language))
        return
    # an open prompt is closed together with the save; otherwise (old user / closed prompt)
    # the number is still accepted
    if await _close_prompt(telegram_id, phone=phone) is None:
        await _save_phone(telegram_id, phone)
    await message.answer(_s("saved", language), reply_markup=_ordinary_keyboard(language))


@router.message(F.text.in_(_SKIP_LABELS))
async def skip_handler(message: Message) -> None:
    if message.from_user is None:
        return
    language = await _close_prompt(message.from_user.id)
    if language is None:
        # no open prompt: a leftover keyboard button. Quietly remove it; never parse it as a spend.
        language = await _user_language(message.from_user.id)
        if language is None:
            raise SkipHandler  # a stranger: ordinary text
    await message.answer(_s("skipped", language), reply_markup=_ordinary_keyboard(language))
