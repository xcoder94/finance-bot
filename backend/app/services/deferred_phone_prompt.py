"""Deferred phone request (PRD-ux U7, work/db/ux-p6-delta.md).

A user registered under the new rules has users.phone_prompt_eligible_at set. After the
commit of an operation of that user, if it is the 3rd recorded one, the phone request is
sent once to the bot chat. Event-driven (SQLAlchemy session events), no scheduler.

Hot path: the decision is first made on the already loaded User row (is_candidate); for
every existing user (eligible_at IS NULL) it is false and nothing else happens. Only a
candidate costs one LIMIT-3 count and, at >= 3, one race-safe UPDATE ... RETURNING that
claims the send. If the send fails after the claim the user is not asked again.

The phone number is never logged.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.config import BOT_TOKEN
from app.db import async_session_factory
from app.models.transaction import Transaction
from app.models.user import User

logger = logging.getLogger(__name__)

PROMPT_AFTER_OPERATIONS = 3
# The prompt must arrive after the reply to the operation, not before it.
SEND_DELAY_SECONDS = 1.5

_AUTHORS_KEY = "deferred_phone_prompt_authors"
_tasks: set[asyncio.Task[None]] = set()


@dataclass(frozen=True)
class Claimed:
    telegram_id: int
    language: str


def is_candidate(user: Any) -> bool:
    return (
        user.phone_prompt_eligible_at is not None
        and user.phone_prompted_at is None
        and user.phone is None
        and not user.is_deleted
    )


async def claim(session: Any, user_id: uuid.UUID) -> Claimed | None:
    """Count the user's recorded operations; at >= 3 claim the single send. No commit here."""
    count = await session.scalar(
        text(
            "SELECT count(*) FROM (SELECT 1 FROM transactions "
            "WHERE created_by_user_id = :u AND NOT is_demo LIMIT :n) x"
        ),
        {"u": user_id, "n": PROMPT_AFTER_OPERATIONS},
    )
    if (count or 0) < PROMPT_AFTER_OPERATIONS:
        return None
    row = (
        await session.execute(
            text(
                "UPDATE users SET phone_prompted_at = now() WHERE id = :u "
                "AND phone_prompt_eligible_at IS NOT NULL AND phone_prompted_at IS NULL "
                "AND phone IS NULL AND NOT is_deleted RETURNING telegram_id, language"
            ),
            {"u": user_id},
        )
    ).first()
    if row is None:
        return None
    return Claimed(telegram_id=row.telegram_id, language=row.language)


async def _bot_send(telegram_id: int, language: str) -> None:
    from aiogram import Bot

    from bot.phone_prompt import prompt_keyboard, prompt_text

    bot = Bot(token=BOT_TOKEN)
    try:
        await bot.send_message(
            telegram_id, prompt_text(language), reply_markup=prompt_keyboard(language)
        )
    finally:
        await bot.session.close()


async def send_prompt(claimed: Claimed) -> None:
    try:
        await _bot_send(claimed.telegram_id, claimed.language)
    except Exception:
        # Already claimed: "once" wins, refusing or missing the prompt blocks nothing.
        logger.warning("deferred phone prompt not delivered", exc_info=True)


async def run_for_user(user_id: uuid.UUID) -> None:
    try:
        if SEND_DELAY_SECONDS:
            await asyncio.sleep(SEND_DELAY_SECONDS)
        async with async_session_factory() as session:
            claimed = await claim(session, user_id)
            await session.commit()
        if claimed is not None:
            await send_prompt(claimed)
    except Exception:
        logger.exception("deferred phone prompt check failed")


async def drain() -> None:
    """Wait for scheduled checks (tests, graceful shutdown)."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)


def _schedule(user_id: uuid.UUID) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = loop.create_task(run_for_user(user_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def _on_after_flush(session: Session, _ctx: Any) -> None:
    authors: set[uuid.UUID] = session.info.setdefault(_AUTHORS_KEY, set())
    for obj in session.new:
        if isinstance(obj, Transaction) and not obj.is_demo and obj.created_by_user_id:
            authors.add(obj.created_by_user_id)


def _on_after_commit(session: Session) -> None:
    authors: set[uuid.UUID] = session.info.pop(_AUTHORS_KEY, set())
    for user_id in authors:
        user = session.identity_map.get(_user_key(user_id))
        # Not loaded in this session -> not checked: the author is always the loaded actor
        # of the request/handler; we never add a query for it.
        if user is not None and is_candidate(user):
            _schedule(user_id)


def _on_after_rollback(session: Session) -> None:
    session.info.pop(_AUTHORS_KEY, None)


def _user_key(user_id: uuid.UUID) -> Any:
    from sqlalchemy.orm.util import identity_key

    return identity_key(User, user_id)


def install() -> None:
    for name, fn in (
        ("after_flush", _on_after_flush),
        ("after_commit", _on_after_commit),
        ("after_rollback", _on_after_rollback),
    ):
        if not event.contains(Session, name, fn):
            event.listen(Session, name, fn)


install()
