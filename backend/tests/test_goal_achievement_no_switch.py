"""Goal achievement is independent of notification preference switches (§12.3 / §16.3)."""

import socket
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.goal import Goal
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.goal_notify import format_achievement_message
from tests.test_wallets_categories import api_client, auth_headers, create_user_with_budget


def _db_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            return True
    except OSError:
        return False


def _random_tid() -> int:
    return int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000


async def _create_owner_and_member_both_switches_off(
    session: AsyncSession,
) -> tuple[int, int, User, User]:
    owner_tid = _random_tid()
    member_tid = owner_tid + 1
    owner, budget = await create_user_with_budget(
        session, telegram_id=owner_tid, role="owner"
    )
    owner.evening_reminder_enabled = False
    owner.weekly_digest_enabled = False
    member = User(
        telegram_id=member_tid,
        family_budget_id=budget.id,
        role="member",
        language="ru",
        evening_reminder_enabled=False,
        weekly_digest_enabled=False,
    )
    session.add(member)
    await session.flush()
    return owner_tid, member_tid, owner, member


async def _create_shared_wallet(
    session: AsyncSession,
    budget_id: uuid.UUID,
    *,
    name: str = "Накопления",
) -> Wallet:
    wallet = Wallet(
        family_budget_id=budget_id,
        name=name,
        currency="UZS",
        is_personal=False,
    )
    session.add(wallet)
    await session.flush()
    return wallet


async def _seed_income(
    session: AsyncSession,
    budget_id: uuid.UUID,
    wallet_id: uuid.UUID,
    user_id: uuid.UUID,
    amount: int,
) -> None:
    income_cat = IncomeCategory(family_budget_id=budget_id, name="Salary")
    session.add(income_cat)
    await session.flush()
    session.add(
        Transaction(
            family_budget_id=budget_id,
            type="income",
            wallet_id=wallet_id,
            amount=amount,
            income_category_id=income_cat.id,
            created_by_user_id=user_id,
            transaction_date=datetime(2026, 4, 1, 12, 0, tzinfo=UTC),
        )
    )
    await session.flush()


def _mock_bot(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    bot = AsyncMock()
    bot.send_message = AsyncMock()

    async def fake_resolve_bot(b: AsyncMock | None) -> tuple[AsyncMock, bool]:
        return (bot if b is None else b), False

    monkeypatch.setattr("app.services.goals.resolve_bot", fake_resolve_bot)
    monkeypatch.setattr("app.services.goal_notify.resolve_bot", fake_resolve_bot)
    return bot


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_achievement_sends_despite_both_notification_switches_off(
    api_client: tuple[AsyncClient, AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = api_client
    owner_tid, member_tid, owner, member = await _create_owner_and_member_both_switches_off(
        session
    )
    assert owner.evening_reminder_enabled is False
    assert owner.weekly_digest_enabled is False
    assert member.evening_reminder_enabled is False
    assert member.weekly_digest_enabled is False

    wallet = await _create_shared_wallet(session, owner.family_budget_id)
    await _seed_income(session, owner.family_budget_id, wallet.id, owner.id, 8_200_000)
    await session.flush()

    bot = _mock_bot(monkeypatch)

    resp = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={"wallet_id": str(wallet.id), "target_amount": 8_000_000},
    )
    assert resp.status_code == 201, resp.text
    goal_id = uuid.UUID(resp.json()["id"])

    expected_text = format_achievement_message("Накопления", 8_200_000, 8_000_000, "UZS")

    assert bot.send_message.await_count == 2
    calls_by_tid: dict[int, tuple] = {
        c.args[0]: (c.args[1], c.kwargs) for c in bot.send_message.await_args_list
    }
    assert owner_tid in calls_by_tid
    assert member_tid in calls_by_tid

    owner_text, owner_kwargs = calls_by_tid[owner_tid]
    member_text, member_kwargs = calls_by_tid[member_tid]
    assert owner_text == expected_text
    assert member_text == expected_text

    owner_markup = owner_kwargs["reply_markup"]
    member_markup = member_kwargs["reply_markup"]
    assert owner_markup is not None
    assert owner_markup.inline_keyboard[0][0].text == "Закрыть цель"
    assert owner_markup.inline_keyboard[0][0].callback_data == f"goal:close:{goal_id}"
    assert member_markup is None

    goal = await session.get(Goal, goal_id)
    assert goal is not None
    assert goal.crossed is True
