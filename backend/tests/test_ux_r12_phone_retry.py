"""ux-r12: the phone request is not repeated on every operation when Telegram fails (security r2 L3)."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from aiogram.exceptions import TelegramForbiddenError
from aiogram.methods import SendMessage
from sqlalchemy import text

from app.services import deferred_phone_prompt as dpp
from app.services import goal_notify
from tests.test_quick_entry_flow import rollback_session
from tests.test_ux_p6_phone import _add_ops, _eligible_user, _Same
from tests.test_ux_r11_mixed_dates_and_phone import _patch_bot
from tests.test_quick_entry_flow import pytestmark  # noqa: F401


async def _ops(session, user, budget, wallet, monkeypatch, n) -> None:  # noqa: ANN001
    monkeypatch.setattr(dpp, "SEND_DELAY_SECONDS", 0)
    monkeypatch.setattr(dpp, "async_session_factory", lambda: _Same(session))
    for _ in range(n):
        await _add_ops(session, user, budget, wallet, 1)
        await session.commit()
        await dpp.drain()


async def _a_day_passes(session, user) -> None:  # noqa: ANN001
    """Everything the person has been through moves 25 hours into the past."""
    await session.execute(
        text(
            "UPDATE users SET created_at = created_at - interval '25 hours', "
            "phone_prompt_eligible_at = phone_prompt_eligible_at - interval '25 hours' "
            "WHERE id = :u"
        ),
        {"u": user.id},
    )
    await session.commit()
    await session.refresh(user)


def _blocked(*_a, **_k):  # noqa: ANN002, ANN003
    raise TelegramForbiddenError(
        method=SendMessage(chat_id=1, text="x"), message="Forbidden: bot was blocked by the user"
    )


async def test_blocked_bot_is_asked_once_not_on_every_operation(monkeypatch) -> None:
    bot = _patch_bot(monkeypatch, _blocked)
    async with rollback_session() as session:
        user, budget, wallet = await _eligible_user(session, tid=9_612_001)
        await _ops(session, user, budget, wallet, monkeypatch, 20)
        assert bot.send_message.await_count == 1
        await _a_day_passes(session, user)
        await _ops(session, user, budget, wallet, monkeypatch, 3)
        assert bot.send_message.await_count == 1  # blocked: never again, not even tomorrow


async def test_slow_telegram_does_not_make_the_person_get_the_request_again(monkeypatch) -> None:
    async def slow(*_a, **_k):  # noqa: ANN002, ANN003
        await asyncio.sleep(30)

    monkeypatch.setattr(goal_notify, "NOTICE_TIMEOUT_SECONDS", 0.05)
    bot = _patch_bot(monkeypatch, slow)
    async with rollback_session() as session:
        user, budget, wallet = await _eligible_user(session, tid=9_612_002)
        await _ops(session, user, budget, wallet, monkeypatch, 6)
        assert bot.send_message.await_count == 1


async def test_failed_send_is_retried_at_most_once_a_day_and_three_times_in_all(monkeypatch) -> None:
    async def down(*_a, **_k):  # noqa: ANN002, ANN003
        raise RuntimeError("telegram down")

    bot = _patch_bot(monkeypatch, down)
    async with rollback_session() as session:
        user, budget, wallet = await _eligible_user(session, tid=9_612_003)
        await _ops(session, user, budget, wallet, monkeypatch, 8)
        assert bot.send_message.await_count == 1  # same day: one try
        for expected in (2, 3, 3, 3):
            await _a_day_passes(session, user)
            await _ops(session, user, budget, wallet, monkeypatch, 3)
            assert bot.send_message.await_count == expected, expected


async def test_delivered_request_is_never_repeated(monkeypatch) -> None:
    bot = _patch_bot(monkeypatch, AsyncMock())
    async with rollback_session() as session:
        user, budget, wallet = await _eligible_user(session, tid=9_612_004)
        await _ops(session, user, budget, wallet, monkeypatch, 5)
        await _a_day_passes(session, user)
        await _ops(session, user, budget, wallet, monkeypatch, 3)
        assert bot.send_message.await_count == 1
