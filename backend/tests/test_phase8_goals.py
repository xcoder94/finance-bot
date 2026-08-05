import socket
import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.goal import Goal
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.goal_notify import format_achievement_message
from app.services.goals import check_goal_achievement
from app.services.quick_entry_balance import wallet_balance
from bot.goals import handle_goal_close
from bot.quick_entry.cards import format_card
from tests.test_wallets_categories import api_client, auth_headers, create_user_with_budget


def _db_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            return True
    except OSError:
        return False


def _random_tid() -> int:
    return int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000


async def _create_owner_and_member(
    session: AsyncSession,
) -> tuple[int, int, User, User]:
    owner_tid = _random_tid()
    member_tid = owner_tid + 1
    owner, budget = await create_user_with_budget(
        session, telegram_id=owner_tid, role="owner"
    )
    member = User(
        telegram_id=member_tid,
        family_budget_id=budget.id,
        role="member",
        language="ru",
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


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_goal_model_roundtrip(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    telegram_id = _random_tid()
    owner, budget = await create_user_with_budget(
        session, telegram_id=telegram_id, role="owner"
    )
    wallet = Wallet(
        family_budget_id=budget.id,
        name="Накопления",
        currency="UZS",
        is_personal=False,
    )
    session.add(wallet)
    await session.flush()
    goal = Goal(
        family_budget_id=budget.id,
        wallet_id=wallet.id,
        name="Накопления",
        target_amount=8_000_000,
        currency="UZS",
        deadline=None,
        status="active",
        crossed=False,
    )
    session.add(goal)
    await session.commit()
    await session.refresh(goal)
    assert goal.id is not None
    assert goal.status == "active"
    assert goal.crossed is False


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_owner_creates_goal_default_name(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid = _random_tid()
    owner, budget = await create_user_with_budget(
        session, telegram_id=owner_tid, role="owner"
    )
    wallet = await _create_shared_wallet(session, budget.id, name="Накопления")
    await session.flush()

    resp = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={"wallet_id": str(wallet.id), "target_amount": 8_000_000},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Накопления"
    assert body["wallet_id"] == str(wallet.id)
    assert body["status"] == "active"
    assert body["can_close"] is True


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_member_cannot_create_goal(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid, member_tid, owner, _ = await _create_owner_and_member(session)
    wallet = await _create_shared_wallet(session, owner.family_budget_id)
    await session.flush()

    resp = await client.post(
        "/api/v1/goals",
        headers=auth_headers(member_tid),
        json={"wallet_id": str(wallet.id), "target_amount": 1_000_000},
    )
    assert resp.status_code == 403


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_create_rejects_personal_wallet(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid, member_tid, owner, member = await _create_owner_and_member(session)
    personal = Wallet(
        family_budget_id=owner.family_budget_id,
        name="Личный",
        currency="UZS",
        is_personal=True,
        owner_user_id=member.id,
    )
    session.add(personal)
    await session.flush()

    resp = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={"wallet_id": str(personal.id), "target_amount": 1_000_000},
    )
    assert resp.status_code == 400


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_second_active_goal_same_wallet_409(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid = _random_tid()
    owner, budget = await create_user_with_budget(
        session, telegram_id=owner_tid, role="owner"
    )
    wallet = await _create_shared_wallet(session, budget.id)
    await session.flush()

    first = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={"wallet_id": str(wallet.id), "target_amount": 1_000_000},
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={"wallet_id": str(wallet.id), "target_amount": 2_000_000},
    )
    assert second.status_code == 409


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_list_active_and_closed(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid = _random_tid()
    owner, budget = await create_user_with_budget(
        session, telegram_id=owner_tid, role="owner"
    )
    wallet_a = await _create_shared_wallet(session, budget.id, name="A")
    wallet_b = await _create_shared_wallet(session, budget.id, name="B")
    await session.flush()

    active_resp = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={"wallet_id": str(wallet_a.id), "target_amount": 1_000_000},
    )
    assert active_resp.status_code == 201
    active_id = active_resp.json()["id"]

    closed_resp = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={"wallet_id": str(wallet_b.id), "target_amount": 2_000_000},
    )
    assert closed_resp.status_code == 201
    closed_id = closed_resp.json()["id"]
    close = await client.post(
        f"/api/v1/goals/{closed_id}/close",
        headers=auth_headers(owner_tid),
    )
    assert close.status_code == 200

    list_active = await client.get(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        params={"status": "active"},
    )
    assert list_active.status_code == 200
    active_ids = {g["id"] for g in list_active.json()}
    assert active_id in active_ids
    assert closed_id not in active_ids
    active_goal = next(g for g in list_active.json() if g["id"] == active_id)
    assert active_goal["progress_pct"] is not None

    list_closed = await client.get(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        params={"status": "closed"},
    )
    assert list_closed.status_code == 200
    closed_ids = {g["id"] for g in list_closed.json()}
    assert closed_id in closed_ids
    assert active_id not in closed_ids
    closed_goal = next(g for g in list_closed.json() if g["id"] == closed_id)
    assert closed_goal["progress_pct"] is None
    assert closed_goal["status"] == "closed"


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_owner_closes_goal_freezes_and_frees_wallet(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid = _random_tid()
    owner, budget = await create_user_with_budget(
        session, telegram_id=owner_tid, role="owner"
    )
    wallet = await _create_shared_wallet(session, budget.id)
    await _seed_income(session, budget.id, wallet.id, owner.id, 500_000)
    await session.flush()
    balance_before = await wallet_balance(session, wallet.id)

    create_resp = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={"wallet_id": str(wallet.id), "target_amount": 1_000_000},
    )
    assert create_resp.status_code == 201
    goal_id = create_resp.json()["id"]

    close_resp = await client.post(
        f"/api/v1/goals/{goal_id}/close",
        headers=auth_headers(owner_tid),
    )
    assert close_resp.status_code == 200
    closed = close_resp.json()
    assert closed["status"] == "closed"
    assert closed["balance"] == balance_before
    assert closed["progress_pct"] is None
    assert await wallet_balance(session, wallet.id) == balance_before

    new_goal = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={"wallet_id": str(wallet.id), "target_amount": 2_000_000},
    )
    assert new_goal.status_code == 201


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_member_cannot_close(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid, member_tid, owner, _ = await _create_owner_and_member(session)
    wallet = await _create_shared_wallet(session, owner.family_budget_id)
    await session.flush()

    create_resp = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={"wallet_id": str(wallet.id), "target_amount": 1_000_000},
    )
    assert create_resp.status_code == 201
    goal_id = create_resp.json()["id"]

    close_resp = await client.post(
        f"/api/v1/goals/{goal_id}/close",
        headers=auth_headers(member_tid),
    )
    assert close_resp.status_code == 403


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
@patch("app.services.goals.tashkent_today", return_value=date(2026, 8, 5))
async def test_create_rejects_backdated_deadline(
    _mock_today: object,
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid = _random_tid()
    owner, budget = await create_user_with_budget(
        session, telegram_id=owner_tid, role="owner"
    )
    wallet = await _create_shared_wallet(session, budget.id)
    await session.flush()

    past = date(2026, 8, 4)
    resp = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={
            "wallet_id": str(wallet.id),
            "target_amount": 1_000_000,
            "deadline": past.isoformat(),
        },
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "deadline_before_today"


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
@patch("app.services.goals.tashkent_today", return_value=date(2026, 8, 5))
async def test_create_accepts_today_and_future_deadline(
    _mock_today: object,
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid = _random_tid()
    owner, budget = await create_user_with_budget(
        session, telegram_id=owner_tid, role="owner"
    )
    wallet_today = await _create_shared_wallet(session, budget.id, name="Today")
    wallet_future = await _create_shared_wallet(session, budget.id, name="Future")
    await session.flush()

    today_resp = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={
            "wallet_id": str(wallet_today.id),
            "target_amount": 1_000_000,
            "deadline": "2026-08-05",
        },
    )
    assert today_resp.status_code == 201, today_resp.text
    assert today_resp.json()["deadline"] == "2026-08-05"

    future_resp = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={
            "wallet_id": str(wallet_future.id),
            "target_amount": 2_000_000,
            "deadline": "2026-12-31",
        },
    )
    assert future_resp.status_code == 201, future_resp.text
    assert future_resp.json()["deadline"] == "2026-12-31"


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
@patch("app.services.goals.tashkent_today", return_value=date(2026, 8, 5))
async def test_patch_rejects_new_backdated_deadline(
    _mock_today: object,
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid = _random_tid()
    owner, budget = await create_user_with_budget(
        session, telegram_id=owner_tid, role="owner"
    )
    wallet = await _create_shared_wallet(session, budget.id)
    await session.flush()

    create_resp = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={"wallet_id": str(wallet.id), "target_amount": 1_000_000},
    )
    assert create_resp.status_code == 201
    goal_id = create_resp.json()["id"]

    past = date(2026, 8, 4)
    patch_resp = await client.patch(
        f"/api/v1/goals/{goal_id}",
        headers=auth_headers(owner_tid),
        json={"deadline": past.isoformat()},
    )
    assert patch_resp.status_code == 400
    assert patch_resp.json()["detail"] == "deadline_before_today"


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
@patch("app.services.goals.tashkent_today", return_value=date(2026, 8, 5))
async def test_patch_allows_keeping_existing_past_deadline(
    _mock_today: object,
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid = _random_tid()
    owner, budget = await create_user_with_budget(
        session, telegram_id=owner_tid, role="owner"
    )
    wallet = await _create_shared_wallet(session, budget.id)
    await session.flush()

    create_resp = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={"wallet_id": str(wallet.id), "target_amount": 1_000_000},
    )
    assert create_resp.status_code == 201
    goal_id = uuid.UUID(create_resp.json()["id"])

    past = date(2026, 8, 1)
    goal = await session.get(Goal, goal_id)
    assert goal is not None
    goal.deadline = past
    await session.commit()

    patch_resp = await client.patch(
        f"/api/v1/goals/{goal_id}",
        headers=auth_headers(owner_tid),
        json={"deadline": past.isoformat(), "target_amount": 1_100_000},
    )
    assert patch_resp.status_code == 200
    body = patch_resp.json()
    assert body["deadline"] == past.isoformat()
    assert body["target_amount"] == 1_100_000


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
@patch("app.services.goals.tashkent_today", return_value=date(2026, 8, 5))
async def test_goal_with_passed_deadline_stays_active_with_label(
    _mock_today: object,
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid = _random_tid()
    owner, budget = await create_user_with_budget(
        session, telegram_id=owner_tid, role="owner"
    )
    wallet = await _create_shared_wallet(session, budget.id)
    await session.flush()

    create_resp = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={"wallet_id": str(wallet.id), "target_amount": 1_000_000},
    )
    assert create_resp.status_code == 201
    goal_id = uuid.UUID(create_resp.json()["id"])

    past = date(2026, 8, 1)
    goal = await session.get(Goal, goal_id)
    assert goal is not None
    goal.deadline = past
    await session.commit()

    list_resp = await client.get(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        params={"status": "active"},
    )
    assert list_resp.status_code == 200
    listed = next(item for item in list_resp.json() if item["id"] == str(goal_id))
    assert listed["status"] == "active"
    assert listed["deadline"] == past.isoformat()

    close_resp = await client.post(
        f"/api/v1/goals/{goal_id}/close",
        headers=auth_headers(owner_tid),
    )
    assert close_resp.status_code == 200


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
async def test_format_achievement_message_uzs() -> None:
    text = format_achievement_message("Накопления", 8_200_000, 8_000_000, "UZS")
    assert text == (
        "🎯 Цель «Накопления» достигнута\n"
        "Накоплено 8 200 000 сум из 8 000 000"
    )


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_crossing_sends_to_every_member_owner_button(
    api_client: tuple[AsyncClient, AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = api_client
    owner_tid, member_tid, owner, _ = await _create_owner_and_member(session)
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

    assert bot.send_message.await_count == 2
    calls_by_tid: dict[int, tuple] = {
        c.args[0]: (c.args[1], c.kwargs) for c in bot.send_message.await_args_list
    }
    assert owner_tid in calls_by_tid
    assert member_tid in calls_by_tid
    owner_text, owner_kwargs = calls_by_tid[owner_tid]
    member_text, member_kwargs = calls_by_tid[member_tid]
    assert owner_text == member_text
    assert "🎯 Цель «Накопления» достигнута" in owner_text
    owner_markup = owner_kwargs["reply_markup"]
    member_markup = member_kwargs["reply_markup"]
    assert owner_markup is not None
    assert owner_markup.inline_keyboard[0][0].text == "Закрыть цель"
    assert owner_markup.inline_keyboard[0][0].callback_data == f"goal:close:{goal_id}"
    assert member_markup is None

    goal = await session.get(Goal, goal_id)
    assert goal is not None
    assert goal.crossed is True


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_staying_above_does_not_resend(
    api_client: tuple[AsyncClient, AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = api_client
    owner_tid, member_tid, owner, _ = await _create_owner_and_member(session)
    wallet = await _create_shared_wallet(session, owner.family_budget_id)
    await _seed_income(session, owner.family_budget_id, wallet.id, owner.id, 8_200_000)
    await session.flush()

    bot = _mock_bot(monkeypatch)

    create_resp = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={"wallet_id": str(wallet.id), "target_amount": 8_000_000},
    )
    assert create_resp.status_code == 201
    assert bot.send_message.await_count == 2

    bot.send_message.reset_mock()
    await check_goal_achievement(session, wallet.id, bot=bot)
    bot.send_message.assert_not_awaited()


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_drop_below_then_cross_sends_again(
    api_client: tuple[AsyncClient, AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = api_client
    owner_tid, member_tid, owner, _ = await _create_owner_and_member(session)
    wallet = await _create_shared_wallet(session, owner.family_budget_id)
    await _seed_income(session, owner.family_budget_id, wallet.id, owner.id, 8_200_000)
    await session.flush()

    bot = _mock_bot(monkeypatch)

    create_resp = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={"wallet_id": str(wallet.id), "target_amount": 8_000_000},
    )
    assert create_resp.status_code == 201
    goal_id = uuid.UUID(create_resp.json()["id"])
    bot.send_message.reset_mock()

    patch_resp = await client.patch(
        f"/api/v1/goals/{goal_id}",
        headers=auth_headers(owner_tid),
        json={"target_amount": 9_000_000},
    )
    assert patch_resp.status_code == 200
    bot.send_message.assert_not_awaited()

    goal = await session.get(Goal, goal_id)
    assert goal is not None
    assert goal.crossed is False

    patch_back = await client.patch(
        f"/api/v1/goals/{goal_id}",
        headers=auth_headers(owner_tid),
        json={"target_amount": 8_000_000},
    )
    assert patch_back.status_code == 200
    assert bot.send_message.await_count == 2


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_close_via_callback_owner(
    api_client: tuple[AsyncClient, AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = api_client
    owner_tid, member_tid, owner, _ = await _create_owner_and_member(session)
    wallet = await _create_shared_wallet(session, owner.family_budget_id)
    await _seed_income(session, owner.family_budget_id, wallet.id, owner.id, 1_000_000)
    await session.flush()

    _mock_bot(monkeypatch)

    create_resp = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={"wallet_id": str(wallet.id), "target_amount": 500_000},
    )
    assert create_resp.status_code == 201
    goal_id = create_resp.json()["id"]

    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=owner_tid),
        message=SimpleNamespace(edit_reply_markup=AsyncMock()),
        data=f"goal:close:{goal_id}",
        answer=AsyncMock(),
    )

    class _SessionCtx:
        async def __aenter__(self) -> AsyncSession:
            return session

        async def __aexit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(
        "bot.goals.async_session_factory",
        lambda: _SessionCtx(),
    )

    await handle_goal_close(callback)
    callback.answer.assert_awaited()
    callback.message.edit_reply_markup.assert_awaited_with(reply_markup=None)

    goal = await session.get(Goal, uuid.UUID(goal_id))
    assert goal is not None
    assert goal.status == "closed"


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_close_via_callback_member_ignored(
    api_client: tuple[AsyncClient, AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = api_client
    owner_tid, member_tid, owner, _ = await _create_owner_and_member(session)
    wallet = await _create_shared_wallet(session, owner.family_budget_id)
    await session.flush()

    create_resp = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={"wallet_id": str(wallet.id), "target_amount": 1_000_000},
    )
    assert create_resp.status_code == 201
    goal_id = create_resp.json()["id"]

    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=member_tid),
        message=SimpleNamespace(edit_reply_markup=AsyncMock()),
        data=f"goal:close:{goal_id}",
        answer=AsyncMock(),
    )

    class _SessionCtx:
        async def __aenter__(self) -> AsyncSession:
            return session

        async def __aexit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(
        "bot.goals.async_session_factory",
        lambda: _SessionCtx(),
    )

    await handle_goal_close(callback)
    callback.answer.assert_awaited()
    callback.message.edit_reply_markup.assert_not_awaited()

    goal = await session.get(Goal, uuid.UUID(goal_id))
    assert goal is not None
    assert goal.status == "active"


def test_quick_entry_card_has_no_goal_progress() -> None:
    text = format_card(
        sign="➖",
        amount=25_000,
        currency="UZS",
        category_label="Такси",
        comment="такси до работы",
        wallet_name="Наличный сум",
        op_date=date(2026, 8, 1),
        balance=1_275_000,
    )
    assert "Цель" not in text


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_transfer_into_wallet_triggers_achievement(
    api_client: tuple[AsyncClient, AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = api_client
    owner_tid, member_tid, owner, _ = await _create_owner_and_member(session)
    wallet_from = await _create_shared_wallet(session, owner.family_budget_id, name="Источник")
    wallet_to = await _create_shared_wallet(session, owner.family_budget_id, name="Накопления")
    await _seed_income(session, owner.family_budget_id, wallet_from.id, owner.id, 1_000)
    await session.flush()

    bot = _mock_bot(monkeypatch)

    goal_resp = await client.post(
        "/api/v1/goals",
        headers=auth_headers(owner_tid),
        json={"wallet_id": str(wallet_to.id), "target_amount": 1_000},
    )
    assert goal_resp.status_code == 201, goal_resp.text
    bot.send_message.reset_mock()

    transfer_resp = await client.post(
        "/api/v1/transactions/transfer",
        headers=auth_headers(owner_tid),
        json={
            "wallet_id": str(wallet_from.id),
            "to_wallet_id": str(wallet_to.id),
            "amount": 1_000,
            "transaction_date": "2026-04-01T12:00:00+00:00",
        },
    )
    assert transfer_resp.status_code == 201, transfer_resp.text
    assert bot.send_message.await_count == 2
    calls_by_tid = {c.args[0] for c in bot.send_message.await_args_list}
    assert owner_tid in calls_by_tid
    assert member_tid in calls_by_tid


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_wallet_list_includes_has_active_goal(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    telegram_id = _random_tid()
    _, budget = await create_user_with_budget(
        session, telegram_id=telegram_id, role="owner"
    )
    wallet_with_goal = await _create_shared_wallet(session, budget.id, name="С целью")
    wallet_without_goal = await _create_shared_wallet(
        session, budget.id, name="Без цели"
    )
    session.add(
        Goal(
            family_budget_id=budget.id,
            wallet_id=wallet_with_goal.id,
            name="Накопления",
            target_amount=1_000_000,
            currency="UZS",
            deadline=None,
            status="active",
        )
    )
    await session.flush()

    response = await client.get("/api/v1/wallets", headers=auth_headers(telegram_id))
    assert response.status_code == 200
    wallets = {w["id"]: w for w in response.json()}
    assert wallets[str(wallet_with_goal.id)]["has_active_goal"] is True
    assert wallets[str(wallet_without_goal.id)]["has_active_goal"] is False
