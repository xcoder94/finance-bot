import socket
import uuid
from datetime import UTC, date, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.goal import Goal
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.quick_entry_balance import wallet_balance
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
async def test_patch_deadline_in_past_allowed(
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

    past = date(2020, 1, 15)
    patch_resp = await client.patch(
        f"/api/v1/goals/{goal_id}",
        headers=auth_headers(owner_tid),
        json={"deadline": past.isoformat()},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["deadline"] == past.isoformat()
