"""ux-next2 (QA bugs 8, 9): the bot join racing the person's own message; reply language from settings."""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import DATABASE_URL
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.family_guard import FamilyChangedError
from tests.test_ux_r14_write_during_family_change import _purge, _TIDS
from tests.test_wallets_categories import _db_available

pytestmark = [
    pytest.mark.skipif(not _db_available(), reason="postgres not available"),
    pytest.mark.anyio,
]


@pytest.fixture
async def real_engine():
    eng = create_async_engine(DATABASE_URL, pool_size=10)
    yield eng
    await _purge(eng)
    await eng.dispose()


def _tid() -> int:
    tid = int(uuid.uuid4().int % 8_000_000_000) + 1_000_000_000
    _TIDS.append(tid)
    return tid


async def _seed(factory, *, language="ru"):
    """A person alone in his budget (stale daily counters), and a family he is invited to."""
    async with factory() as s:
        old = FamilyBudget(invite_token=f"rc-{uuid.uuid4()}", counters_day=date.today() - timedelta(days=1))
        target = FamilyBudget(invite_token=f"rc-{uuid.uuid4()}")
        s.add_all([old, target])
        await s.flush()
        tid, other = _tid(), _tid()
        owner = User(telegram_id=other, family_budget_id=target.id, role="owner", language="ru")
        me = User(telegram_id=tid, family_budget_id=old.id, role="owner", language=language)
        s.add_all([owner, me])
        await s.flush()
        w = Wallet(family_budget_id=old.id, name="Наличные", currency="UZS", is_personal=False)
        s.add(w)
        await s.flush()
        me.default_wallet_id = w.id
        parent = ExpenseCategory(family_budget_id=old.id, name="Транспорт", translation_key="transport")
        s.add(parent)
        await s.flush()
        s.add(ExpenseCategory(family_budget_id=old.id, name="Такси", parent_id=parent.id, translation_key="taxi"))
        await s.commit()
        return tid, me.id, old.id, target.id, target.invite_token


def _callback(tid: int, token: str):
    msg = SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock(), delete=AsyncMock(),
                          edit_reply_markup=AsyncMock())
    return SimpleNamespace(from_user=SimpleNamespace(id=tid), data=f"join_accept:{token}",
                           message=msg, answer=AsyncMock())


async def test_join_and_own_message_at_the_same_moment_never_deadlock(real_engine, monkeypatch) -> None:
    import bot.membership as membership
    import bot.quick_entry.handlers as handlers

    factory = async_sessionmaker(real_engine, expire_on_commit=False)
    monkeypatch.setattr(membership, "async_session_factory", factory)
    monkeypatch.setattr(handlers, "async_session_factory", factory)
    real_ensure = handlers.ensure_counters_day

    async def slow_counters(*a, **kw):  # keeps the message's first locks open while the join starts
        await real_ensure(*a, **kw)
        await asyncio.sleep(0.15)

    monkeypatch.setattr(handlers, "ensure_counters_day", slow_counters)
    monkeypatch.setattr(handlers, "_check_wallets_after_write", AsyncMock())

    outcomes = {"joined": 0, "refused": 0}
    for _ in range(50):
        tid, user_id, old_id, target_id, token = await _seed(factory)
        cb = _callback(tid, token)
        msg = SimpleNamespace(from_user=SimpleNamespace(id=tid), text="такси 20000", answer=AsyncMock())

        async def own_message():
            return await handlers.handle_quick_entry_text(msg, SimpleNamespace())

        async def join():
            await asyncio.sleep(0.05)
            return await membership.join_accept(cb)

        results = await asyncio.gather(own_message(), join(), return_exceptions=True)
        for r in results:
            # a message cut off by the move is refused cleanly (the bot tells him to resend)
            assert r is None or isinstance(r, FamilyChangedError), repr(r)
        assert cb.message.answer.await_count + cb.message.edit_text.await_count >= 1, "join got no reply"
        async with factory() as s:
            me = await s.get(User, user_id)
            assert me.family_budget_id == target_id, "join rolled back"
            stranded = (await s.scalars(select(Transaction).where(
                Transaction.family_budget_id == old_id))).all()
            assert stranded == []
        outcomes["joined"] += 1
    assert outcomes["joined"] == 50


async def test_failed_join_still_answers_the_person(real_engine, monkeypatch) -> None:
    import bot.membership as membership

    factory = async_sessionmaker(real_engine, expire_on_commit=False)
    monkeypatch.setattr(membership, "async_session_factory", factory)

    async def boom(*a, **kw):
        raise RuntimeError("deadlock detected")

    monkeypatch.setattr(membership, "convert_join_with_own_budget", boom)
    for lang, word in (("ru", "ещё раз"), ("uz", "yana")):
        tid, user_id, old_id, target_id, token = await _seed(factory, language=lang)
        cb = _callback(tid, token)
        await membership.join_accept(cb)
        sent = [c.args[0] for c in cb.message.answer.await_args_list + cb.message.edit_text.await_args_list]
        assert any(word in text for text in sent), sent
        async with factory() as s:
            assert (await s.get(User, user_id)).family_budget_id == old_id


# ---- 9: the language is the person's setting, not the Telegram client's
async def test_family_changed_reply_uses_the_language_in_settings(real_engine, monkeypatch) -> None:
    import bot.main as bmain

    factory = async_sessionmaker(real_engine, expire_on_commit=False)
    monkeypatch.setattr(bmain, "async_session_factory", factory, raising=False)
    for setting, tg_code, word in (("uz", "en", "qayta"), ("ru", "uz", "повтор"), ("uz", "ru", "qayta")):
        tid, *_ = await _seed(factory, language=setting)
        answer = AsyncMock()
        update = SimpleNamespace(
            message=SimpleNamespace(answer=answer, from_user=SimpleNamespace(id=tid, language_code=tg_code)),
            callback_query=None)
        assert await bmain.reply_family_changed(update, FamilyChangedError()) is True
        assert word in answer.await_args.args[0].lower()
