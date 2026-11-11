"""A Telegram failure after a saved change never turns the API answer into an error (ux-r6)."""

import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.goal import Goal
from app.models.transaction import Transaction
from app.services import goal_notify
from tests.test_goal_achievement_no_switch import (
    _create_owner_and_member_both_switches_off,
    _create_shared_wallet,
    _db_available,
    _seed_income,
)
from tests.test_wallets_categories import api_client, auth_headers  # noqa: F401

pytestmark = [
    pytest.mark.skipif(not _db_available(), reason="DB not configured"),
    pytest.mark.anyio,
]


def _failing_bot(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=RuntimeError("telegram down"))

    async def fake_resolve_bot(b):  # noqa: ANN001
        return (bot if b is None else b), False

    monkeypatch.setattr("app.services.goal_notify.resolve_bot", fake_resolve_bot)
    return bot


async def test_goal_create_already_achieved_survives_telegram_failure(
    api_client: tuple[AsyncClient, AsyncSession], monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    client, session = api_client
    owner_tid, _m, owner, _ = await _create_owner_and_member_both_switches_off(session)
    wallet = await _create_shared_wallet(session, owner.family_budget_id)
    await _seed_income(session, owner.family_budget_id, wallet.id, owner.id, 9_000_000)
    bot = _failing_bot(monkeypatch)

    resp = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={"wallet_id": str(wallet.id), "target_amount": 8_000_000},
    )
    assert resp.status_code == 201, resp.text
    await goal_notify.drain_background()
    assert bot.send_message.await_count == 2  # every member was tried
    count = await session.scalar(
        select(func.count()).select_from(Goal).where(Goal.wallet_id == wallet.id)
    )
    assert count == 1
    goal = await session.get(Goal, uuid.UUID(resp.json()["id"]))
    await session.refresh(goal)
    assert goal.crossed is True  # not retried (and not re-failing) on the next operation


async def test_transfer_crossing_goal_survives_telegram_failure(
    api_client: tuple[AsyncClient, AsyncSession], monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    client, session = api_client
    owner_tid, _m, owner, _ = await _create_owner_and_member_both_switches_off(session)
    src = await _create_shared_wallet(session, owner.family_budget_id, name="Src")
    dst = await _create_shared_wallet(session, owner.family_budget_id, name="Dst")
    await _seed_income(session, owner.family_budget_id, src.id, owner.id, 1_000)
    _failing_bot(monkeypatch)
    g = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={"wallet_id": str(dst.id), "target_amount": 1_000},
    )
    assert g.status_code == 201, g.text

    resp = await client.post(
        "/api/v1/transactions/transfer",
        headers=auth_headers(owner_tid),
        json={
            "wallet_id": str(src.id),
            "to_wallet_id": str(dst.id),
            "amount": 1_000,
            "transaction_date": "2026-04-01T12:00:00+00:00",
        },
    )
    assert resp.status_code == 201, resp.text
    n = await session.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.wallet_id == src.id)
    )
    assert n == 2  # seed income + one transfer, no duplicate


async def test_bot_construction_failure_is_not_a_request_error(
    api_client: tuple[AsyncClient, AsyncSession], monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    client, session = api_client
    owner_tid, _m, owner, _ = await _create_owner_and_member_both_switches_off(session)
    wallet = await _create_shared_wallet(session, owner.family_budget_id)
    await _seed_income(session, owner.family_budget_id, wallet.id, owner.id, 9_000_000)

    def boom(*a, **kw):  # noqa: ANN002, ANN003
        raise ValueError("bad token")

    monkeypatch.setattr(goal_notify, "Bot", boom)
    resp = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={"wallet_id": str(wallet.id), "target_amount": 8_000_000},
    )
    assert resp.status_code == 201, resp.text


async def test_resolve_bot_returns_inert_bot_when_token_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*a, **kw):  # noqa: ANN002, ANN003
        raise ValueError("bad token")

    monkeypatch.setattr(goal_notify, "Bot", boom)
    bot, owned = await goal_notify.resolve_bot(None)
    assert await goal_notify.send_notice_safe(bot, 1, "x") is False
    if owned:
        await bot.session.close()
