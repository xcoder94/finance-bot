"""ux-next3 (QA round 3, bug 4): a registered person's message racing his own join is never
answered with "register via /start" and never silently dropped."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.transaction import Transaction
from app.models.user import User
from app.services.family_guard import FamilyChangedError
from tests.test_ux_next2_join_and_language import (  # noqa: F401  (real_engine is a fixture)
    _callback,
    _seed,
    real_engine,
)
from tests.test_wallets_categories import _db_available

pytestmark = [
    pytest.mark.skipif(not _db_available(), reason="postgres not available"),
    pytest.mark.anyio,
]


@pytest.mark.parametrize("language", ["ru", "uz"])
async def test_message_read_before_the_join_commits_is_never_told_to_register(
    real_engine, monkeypatch, language
) -> None:
    import bot.membership as membership
    import bot.quick_entry.handlers as handlers

    factory = async_sessionmaker(real_engine, expire_on_commit=False)
    monkeypatch.setattr(membership, "async_session_factory", factory)
    monkeypatch.setattr(handlers, "async_session_factory", factory)
    real_get_user = handlers.get_active_user_by_telegram_id

    for _ in range(6):
        tid, user_id, old_id, target_id, token = await _seed(factory, language=language)
        cb = _callback(tid, token)

        async def read_then_join(session, telegram_id):
            # the message has read the person; the join commits right after that
            user = await real_get_user(session, telegram_id)
            await membership.join_accept(cb)
            return user

        monkeypatch.setattr(handlers, "get_active_user_by_telegram_id", read_then_join)
        msg = SimpleNamespace(from_user=SimpleNamespace(id=tid), text="такси 20000", answer=AsyncMock())
        with pytest.raises(FamilyChangedError):  # the bot's error handler asks to resend, in his language
            await handlers.handle_quick_entry_text(msg, SimpleNamespace())
        for call in msg.answer.await_args_list:
            assert "/start" not in call.args[0] and "ro'yxatdan" not in call.args[0]
        async with factory() as s:
            me = await s.get(User, user_id)
            assert me.family_budget_id == target_id
            assert (await s.scalars(select(Transaction).where(Transaction.family_budget_id == old_id))).all() == []
