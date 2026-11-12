"""Deferred phone request (PRD-ux U7, work/db/ux-p6-delta.md).

A user registered under the new rules has users.phone_prompt_eligible_at set. After the
commit of an operation of that user, if it is the 3rd recorded one, the phone request is
sent once to the bot chat. Event-driven (SQLAlchemy session events), no scheduler.

Hot path: the decision is first made on the already loaded User row (is_candidate); for
every existing user (eligible_at IS NULL) it is false and nothing else happens. Only a
candidate costs one LIMIT-3 count and, at >= 3, one race-safe UPDATE ... RETURNING that
claims the send. Delivered -> never again. Bot blocked -> never again. Any other failure
(timeout, network): the request may or may not have arrived, so it is repeated not sooner
than a day later and at most 3 times in all (see _reschedule). No extra columns: the retry
time is kept in phone_prompt_eligible_at ("not before"), the cap is anchored to created_at.

The phone number is never logged.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from dataclasses import dataclass
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.orm import Session

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
    user_id: uuid.UUID | None = None


RETRY_AFTER_HOURS = 24
# Retries stop 3 days after registration: with >= 24 h between tries that is at most 3 tries.
RETRY_WINDOW_HOURS = 72


def is_candidate(user: Any) -> bool:
    return (
        user.phone_prompt_eligible_at is not None
        and user.phone_prompt_eligible_at <= datetime.now(UTC)
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
                "AND phone_prompt_eligible_at IS NOT NULL AND phone_prompt_eligible_at <= clock_timestamp() "
                "AND phone_prompted_at IS NULL "
                "AND phone IS NULL AND NOT is_deleted RETURNING telegram_id, language"
            ),
            {"u": user_id},
        )
    ).first()
    if row is None:
        return None
    return Claimed(telegram_id=row.telegram_id, language=row.language, user_id=user_id)


async def _reschedule(user_id: uuid.UUID, *, give_up: bool) -> None:
    """The request did not (surely) reach the person. Give the claim back, but not for a day;
    after the retry window (or when the bot is blocked) never again."""
    async with async_session_factory() as session:
        await session.execute(
            text(
                "UPDATE users SET phone_prompted_at = NULL, phone_prompt_eligible_at = "
                "CASE WHEN NOT :give_up AND clock_timestamp() + make_interval(hours => :retry) "
                "< created_at + make_interval(hours => :window) "
                "THEN clock_timestamp() + make_interval(hours => :retry) ELSE NULL END "
                "WHERE id = :u AND phone_prompt_closed_at IS NULL AND phone IS NULL "
                "AND phone_prompted_at IS NOT NULL"
            ),
            {
                "u": user_id,
                "give_up": give_up,
                "retry": RETRY_AFTER_HOURS,
                "window": RETRY_WINDOW_HOURS,
            },
        )
        await session.commit()


async def send_prompt(claimed: Claimed) -> None:
    """Same safe path as the other notices (short timeout, errors logged by type only)."""
    from app.services import goal_notify
    from bot.phone_prompt import prompt_keyboard, prompt_text

    bot, owned = await goal_notify.resolve_bot(None)
    try:
        outcome = await goal_notify.send_notice_outcome(
            bot,
            claimed.telegram_id,
            prompt_text(claimed.language),
            reply_markup=prompt_keyboard(claimed.language),
        )
    finally:
        if owned:
            try:
                await bot.session.close()
            except Exception:  # noqa: BLE001
                pass
    if outcome != "delivered" and claimed.user_id is not None:
        try:
            await _reschedule(claimed.user_id, give_up=outcome == "blocked")
        except Exception:  # noqa: BLE001
            logger.warning("deferred phone prompt retry not scheduled", exc_info=True)


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
