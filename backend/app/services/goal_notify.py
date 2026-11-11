import asyncio
import logging
import uuid
from typing import Any

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import BOT_TOKEN
from app.models.goal import Goal
from app.models.user import User
from app.services.bot_texts import t
from bot.quick_entry.cards import format_amount, format_number


def format_achievement_message(
    name: str, balance: int, target: int, currency: str, language: str | None = None
) -> str:
    return t(
        language,
        "goal.achieved",
        name=name,
        balance=format_amount(balance, currency, language),
        target=format_number(target),
    )


def owner_close_keyboard(
    goal_id: uuid.UUID, language: str | None = None
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(language, "goal.close"),
                    callback_data=f"goal:close:{goal_id}",
                )
            ]
        ]
    )


Outbox = list[tuple[int, str, InlineKeyboardMarkup | None]]


async def prepare_achievement(session: AsyncSession, goal: Goal, balance: int) -> Outbox:
    """Messages for every family member, built while the goal is still loaded (before commit)."""
    stmt = select(User).where(
        User.family_budget_id == goal.family_budget_id,
        User.is_deleted.is_(False),
    )
    users = (await session.scalars(stmt)).all()
    outbox: Outbox = []
    for user in users:
        text = format_achievement_message(
            goal.name, balance, goal.target_amount, goal.currency, user.language
        )
        reply_markup = (
            owner_close_keyboard(goal.id, user.language)
            if user.role == "owner"
            else None
        )
        outbox.append((user.telegram_id, text, reply_markup))
    return outbox


async def send_outbox(bot: Bot, outbox: Outbox) -> None:
    for chat_id, text, reply_markup in outbox:
        await send_notice_safe(bot, chat_id, text, reply_markup=reply_markup)


async def fan_out_achievement(
    session: AsyncSession,
    goal: Goal,
    balance: int,
    bot: Bot,
) -> None:
    await send_outbox(bot, await prepare_achievement(session, goal, balance))


class _InertBot:
    """Stand-in when the real Bot cannot be built (bad/missing token): every send fails safely."""

    class session:  # noqa: N801
        @staticmethod
        async def close() -> None:
            return None

    async def send_message(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError("telegram bot unavailable")


async def resolve_bot(bot: Bot | None) -> tuple[Bot, bool]:
    if bot is not None:
        return bot, False
    try:
        return Bot(token=BOT_TOKEN), True
    except Exception as exc:  # noqa: BLE001 - invalid token must not break a saved change
        logging.getLogger(__name__).warning(
            "telegram bot not created: %s", type(exc).__name__
        )
        return _InertBot(), False  # type: ignore[return-value]


async def send_notice_safe(bot: Bot, chat_id: int, text: str, **kwargs: Any) -> bool:
    """Best-effort Telegram notice: a delivery failure never breaks the caller's
    already-decided state change. The error is logged (type only, no text).
    A hanging Telegram is cut off after NOTICE_TIMEOUT_SECONDS."""
    try:
        await asyncio.wait_for(
            bot.send_message(chat_id, text, **kwargs), timeout=NOTICE_TIMEOUT_SECONDS
        )
    except Exception as exc:  # noqa: BLE001 - blocked bot, network, bad token...
        logging.getLogger(__name__).warning(
            "telegram notice to %s not delivered: %s", chat_id, type(exc).__name__
        )
        return False
    return True


# --- Deferred delivery (ux-r7) -------------------------------------------------
# API requests never wait for Telegram: notices are queued on the session and sent by a
# background task only after the outermost commit (rolled back -> dropped).

NOTICE_TIMEOUT_SECONDS = 5.0
_QUEUE_KEY = "notice_queue"
_background_tasks: set[asyncio.Task[None]] = set()

Notice = tuple[int, str, dict[str, Any]]


def queue_notice(
    session: AsyncSession,
    bot: Bot | None,
    chat_id: int,
    text: str,
    **kwargs: Any,
) -> None:
    """Queue a notice; it is sent after the session commits. bot=None -> own Bot at send time."""
    queue = session.sync_session.info.setdefault(_QUEUE_KEY, [])
    queue.append((bot, (chat_id, text, kwargs)))


async def deliver(bot: Bot | None, notices: list[Notice]) -> None:
    resolved, owned = await resolve_bot(bot)
    try:
        await asyncio.gather(
            *(send_notice_safe(resolved, cid, text, **kw) for cid, text, kw in notices)
        )
    except Exception:  # noqa: BLE001 - background task must never raise
        logging.getLogger(__name__).warning("notice delivery failed")
    finally:
        if owned:
            try:
                await resolved.session.close()
            except Exception:  # noqa: BLE001
                pass


def spawn_background(coro: Any) -> None:
    task = asyncio.get_running_loop().create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def drain_background() -> None:
    """Wait for in-flight notice tasks (tests / graceful shutdown)."""
    while _background_tasks:
        await asyncio.gather(*list(_background_tasks), return_exceptions=True)


@event.listens_for(Session, "after_commit")
def _flush_queue_after_commit(session: Session) -> None:
    queue = session.info.pop(_QUEUE_KEY, None)
    if not queue:
        return
    groups: dict[int, tuple[Bot | None, list[Notice]]] = {}
    for bot, notice in queue:
        groups.setdefault(id(bot), (bot, []))[1].append(notice)
    try:
        for bot, notices in groups.values():
            spawn_background(deliver(bot, notices))
    except RuntimeError:  # no running loop: nothing to send with
        pass


@event.listens_for(Session, "after_soft_rollback")
def _drop_queue_on_rollback(session: Session, previous_transaction: Any) -> None:
    if not previous_transaction.nested:  # a savepoint rollback keeps the outer queue
        session.info.pop(_QUEUE_KEY, None)
