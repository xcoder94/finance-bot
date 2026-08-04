import socket
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.goal import Goal
from app.models.wallet import Wallet
from tests.test_wallets_categories import api_client, create_user_with_budget


def _db_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_goal_model_roundtrip(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
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
