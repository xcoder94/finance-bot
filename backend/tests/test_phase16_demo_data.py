import socket
import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine
from app.models.family_budget import FamilyBudget
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from tests.test_wallets_categories import api_client


def _db_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            return True
    except OSError:
        return False


async def _reset_engine() -> None:
    await engine.dispose()


pytestmark = [
    pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available"),
    pytest.mark.anyio,
]


@pytest.mark.anyio
async def test_is_demo_column_exists_not_null_default_false():
    await _reset_engine()
    async with engine.connect() as conn:
        def check(sync_conn):
            cols = {c["name"]: c for c in inspect(sync_conn).get_columns("transactions")}
            assert "is_demo" in cols
            assert cols["is_demo"]["nullable"] is False

        await conn.run_sync(check)


@pytest.mark.anyio
async def test_new_transaction_defaults_is_demo_false(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    _, session = api_client
    budget = FamilyBudget(invite_token=f"test-{uuid.uuid4()}")
    session.add(budget)
    await session.flush()
    wallet = Wallet(
        family_budget_id=budget.id,
        name="Карта сум",
        currency="UZS",
        translation_key="card_uzs",
    )
    user = User(
        telegram_id=int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000,
        family_budget_id=budget.id,
        role="owner",
        language="ru",
    )
    session.add_all([wallet, user])
    await session.flush()
    txn = Transaction(
        family_budget_id=budget.id,
        type="expense",
        wallet_id=wallet.id,
        amount=1000,
        created_by_user_id=user.id,
        transaction_date=datetime.now(UTC),
    )
    session.add(txn)
    await session.flush()
    await session.refresh(txn)
    assert txn.is_demo is False
