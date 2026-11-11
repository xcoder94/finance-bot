"""ux-p6 backend: the phone request is deferred to the 3rd recorded operation (PRD-ux U7).

Real Postgres (rolled-back savepoint sessions); only the Telegram send is replaced.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.models.transaction import Transaction
from app.models.user import User
from app.services import deferred_phone_prompt as dpp
from tests.test_a1_bot_phone import _new_user_callback
from tests.test_quick_entry_flow import (
    create_user,
    make_wallet,
    pytestmark,  # noqa: F401
    rollback_session,
)


async def _eligible_user(session, *, tid=9_610_001):
    user, budget = await create_user(session, telegram_id=tid)
    user.phone_prompt_eligible_at = datetime.now(UTC)
    wallet = make_wallet(budget, name="Наличный сум")
    session.add(wallet)
    await session.flush()
    return user, budget, wallet


async def _add_ops(session, user, budget, wallet, n, *, is_demo=False, is_deleted=False):
    for _ in range(n):
        session.add(Transaction(
            family_budget_id=budget.id, type="expense", wallet_id=wallet.id, amount=1000,
            created_by_user_id=user.id, transaction_date=datetime.now(UTC),
            is_demo=is_demo, is_deleted=is_deleted, channel="text",
        ))
    await session.flush()


# ---------------------------------------------------------------- registration


@pytest.mark.parametrize("language", ["ru", "uz"])
async def test_new_owner_gets_only_welcome_and_is_marked_eligible(monkeypatch, language) -> None:
    from app.services.member_texts import welcome_solo

    async with rollback_session() as session:
        monkeypatch.setattr("bot.onboarding.assign_default_card_uzs", AsyncMock())
        user, message = await _new_user_callback(session, monkeypatch, language=language)
        assert [c.args[0] for c in message.answer.await_args_list] == [welcome_solo(language)]
        assert user.phone_prompted_at is None and user.phone_prompt_closed_at is None
        assert user.phone_prompt_eligible_at is not None


async def test_new_member_gets_only_welcome_and_is_marked_eligible(monkeypatch) -> None:
    from app.services.member_texts import welcome_invited

    async with rollback_session() as session:
        _owner, budget = await create_user(session, telegram_id=9_610_050)
        monkeypatch.setattr("bot.onboarding.assign_default_card_uzs", AsyncMock())
        user, message = await _new_user_callback(
            session, monkeypatch, language="ru", flow="member", budget_id=budget.id
        )
        assert [c.args[0] for c in message.answer.await_args_list] == [welcome_invited(budget.name)]
        assert user.role == "member" and user.phone_prompted_at is None
        assert user.phone_prompt_eligible_at is not None


# ------------------------------------------------------------------ the claim


async def test_claim_fires_once_on_the_third_operation() -> None:
    async with rollback_session() as session:
        user, budget, wallet = await _eligible_user(session)
        await _add_ops(session, user, budget, wallet, 2)
        assert await dpp.claim(session, user.id) is None
        await _add_ops(session, user, budget, wallet, 1)
        claimed = await dpp.claim(session, user.id)
        assert claimed is not None and claimed.telegram_id == user.telegram_id
        assert claimed.language == "ru"
        assert await dpp.claim(session, user.id) is None  # once
        await session.refresh(user)
        assert user.phone_prompted_at is not None and user.phone_prompt_closed_at is None


async def test_demo_operations_do_not_count_deleted_ones_do() -> None:
    async with rollback_session() as session:
        user, budget, wallet = await _eligible_user(session, tid=9_610_002)
        await _add_ops(session, user, budget, wallet, 5, is_demo=True)
        assert await dpp.claim(session, user.id) is None
        await _add_ops(session, user, budget, wallet, 2)
        await _add_ops(session, user, budget, wallet, 1, is_deleted=True)
        assert await dpp.claim(session, user.id) is not None


async def test_existing_user_is_never_asked() -> None:
    async with rollback_session() as session:
        user, budget, wallet = await _eligible_user(session, tid=9_610_003)
        user.phone_prompt_eligible_at = None  # registered before the release
        await _add_ops(session, user, budget, wallet, 5)
        assert await dpp.claim(session, user.id) is None
        await session.refresh(user)
        assert user.phone_prompted_at is None


@pytest.mark.parametrize("state", ["asked", "closed", "has_phone", "deleted"])
async def test_already_handled_users_are_not_asked(state) -> None:
    async with rollback_session() as session:
        user, budget, wallet = await _eligible_user(session, tid=9_610_010 + len(state))
        await _add_ops(session, user, budget, wallet, 4)
        if state in ("asked", "closed"):
            user.phone_prompted_at = datetime.now(UTC)
        if state == "closed":
            user.phone_prompt_closed_at = datetime.now(UTC)
        if state == "has_phone":
            user.phone, user.phone_shared_at = "+998901234567", datetime.now(UTC)
        if state == "deleted":
            user.is_deleted = True
        await session.flush()
        assert await dpp.claim(session, user.id) is None


async def test_is_candidate_uses_only_the_loaded_row() -> None:
    now = datetime.now(UTC)
    base = dict(phone_prompt_eligible_at=now, phone_prompted_at=None, phone=None, is_deleted=False)
    assert dpp.is_candidate(SimpleNamespace(**base))
    for override in ({"phone_prompt_eligible_at": None}, {"phone_prompted_at": now},
                     {"phone": "+998901234567"}, {"is_deleted": True}):
        assert not dpp.is_candidate(SimpleNamespace(**{**base, **override}))


# ------------------------------------------------------------- commit listener


async def test_commit_of_third_operation_triggers_one_prompt(monkeypatch) -> None:
    sent: list = []

    async def fake_send(claimed) -> None:
        sent.append(claimed)

    monkeypatch.setattr(dpp, "send_prompt", fake_send)
    monkeypatch.setattr(dpp, "SEND_DELAY_SECONDS", 0)
    async with rollback_session() as session:
        user, budget, wallet = await _eligible_user(session, tid=9_610_020)
        monkeypatch.setattr(dpp, "async_session_factory", lambda: _Same(session))
        for i in range(3):
            await _add_ops(session, user, budget, wallet, 1)
            await session.commit()
            await dpp.drain()
            assert len(sent) == (1 if i == 2 else 0)
        await _add_ops(session, user, budget, wallet, 1)
        await session.commit()
        await dpp.drain()
        assert len(sent) == 1


async def test_listener_ignores_users_that_are_not_candidates(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(dpp, "run_for_user", lambda uid: calls.append(uid) or asyncio.sleep(0))
    async with rollback_session() as session:
        user, budget, wallet = await _eligible_user(session, tid=9_610_021)
        user.phone_prompt_eligible_at = None
        await _add_ops(session, user, budget, wallet, 1)
        await session.commit()
        await dpp.drain()
        assert calls == []


async def test_send_failure_is_swallowed(monkeypatch) -> None:
    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=RuntimeError("blocked by user"))

    async def fake_resolve_bot(_b):
        return bot, False

    monkeypatch.setattr("app.services.goal_notify.resolve_bot", fake_resolve_bot)
    await dpp.send_prompt(dpp.Claimed(telegram_id=1, language="ru"))  # must not raise


class _Same:
    def __init__(self, session) -> None:
        self._s = session

    async def __aenter__(self):
        return self._s

    async def __aexit__(self, *_a) -> None:
        return None
