import socket
import uuid
from calendar import monthrange
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine
from app.models.family_budget import FamilyBudget
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.budget_seed import copy_seed_data, seed_demo_operations
from app.services.membership_lifecycle import detach_member_to_own_budget
from tests.test_wallets_categories import (
    api_client,
    auth_headers,
    create_user_with_budget,
)


def _db_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            return True
    except OSError:
        return False


async def _reset_engine() -> None:
    await engine.dispose()


def _previous_month_bounds() -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    if now.month == 1:
        year, month = now.year - 1, 12
    else:
        year, month = now.year, now.month - 1
    _, days = monthrange(year, month)
    start = datetime(year, month, 1, 0, 0, tzinfo=UTC)
    end = datetime(year, month, days, 23, 59, 59, tzinfo=UTC)
    return start, end


def _current_month_start() -> datetime:
    now = datetime.now(UTC)
    return datetime(now.year, now.month, 1, 0, 0, tzinfo=UTC)


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


@pytest.mark.anyio
async def test_seed_demo_operations_creates_previous_month_demo_rows(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    _, session = api_client
    owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    owner, budget = await create_user_with_budget(session, telegram_id=owner_tid)
    await copy_seed_data(session, budget.id)
    await seed_demo_operations(session, budget.id, owner.id)
    await session.flush()

    prev_start, prev_end = _previous_month_bounds()
    current_start = _current_month_start()

    demo_rows = (
        await session.scalars(
            select(Transaction).where(
                Transaction.family_budget_id == budget.id,
                Transaction.is_demo.is_(True),
                Transaction.is_deleted.is_(False),
            )
        )
    ).all()
    assert len(demo_rows) == 21
    assert all(row.is_demo for row in demo_rows)
    assert all(prev_start <= row.transaction_date <= prev_end for row in demo_rows)

    current_demo = await session.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(
            Transaction.family_budget_id == budget.id,
            Transaction.is_demo.is_(True),
            Transaction.is_deleted.is_(False),
            Transaction.transaction_date >= current_start,
        )
    )
    assert current_demo == 0

    uzs_expense = await session.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .select_from(Transaction)
        .join(Wallet, Transaction.wallet_id == Wallet.id)
        .where(
            Transaction.family_budget_id == budget.id,
            Transaction.is_demo.is_(True),
            Transaction.is_deleted.is_(False),
            Transaction.type == "expense",
            Wallet.currency == "UZS",
        )
    )
    uzs_income = await session.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .select_from(Transaction)
        .join(Wallet, Transaction.wallet_id == Wallet.id)
        .where(
            Transaction.family_budget_id == budget.id,
            Transaction.is_demo.is_(True),
            Transaction.is_deleted.is_(False),
            Transaction.type == "income",
            Wallet.currency == "UZS",
        )
    )
    usd_expense = await session.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .select_from(Transaction)
        .join(Wallet, Transaction.wallet_id == Wallet.id)
        .where(
            Transaction.family_budget_id == budget.id,
            Transaction.is_demo.is_(True),
            Transaction.is_deleted.is_(False),
            Transaction.type == "expense",
            Wallet.currency == "USD",
        )
    )
    usd_income = await session.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .select_from(Transaction)
        .join(Wallet, Transaction.wallet_id == Wallet.id)
        .where(
            Transaction.family_budget_id == budget.id,
            Transaction.is_demo.is_(True),
            Transaction.is_deleted.is_(False),
            Transaction.type == "income",
            Wallet.currency == "USD",
        )
    )
    assert int(uzs_income or 0) - int(uzs_expense or 0) == 2_000_000
    assert int(usd_income or 0) - int(usd_expense or 0) == 100


@pytest.mark.anyio
async def test_detach_without_personal_wallets_seeds_demo_data(
    api_client: tuple[AsyncClient, AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, session = api_client
    owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    member_tid = owner_tid + 1
    bot = AsyncMock()
    bot.send_message = AsyncMock()

    async def fake_resolve_bot(_bot):
        return bot, False

    monkeypatch.setattr(
        "app.services.membership_lifecycle.resolve_bot", fake_resolve_bot
    )

    owner, budget = await create_user_with_budget(session, telegram_id=owner_tid, role="owner")
    member = User(
        telegram_id=member_tid,
        family_budget_id=budget.id,
        role="member",
        language="ru",
    )
    session.add(member)
    await session.flush()
    await copy_seed_data(session, budget.id)
    await session.flush()

    new_budget = await detach_member_to_own_budget(
        session,
        departing_user=member,
        old_budget=budget,
        reason="left",
        bot=None,
    )
    await session.flush()

    demo_count = await session.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(
            Transaction.family_budget_id == new_budget.id,
            Transaction.is_demo.is_(True),
            Transaction.is_deleted.is_(False),
        )
    )
    assert demo_count == 21


@pytest.mark.anyio
async def test_detach_with_personal_wallets_seeds_demo_after_shared_cards(
    api_client: tuple[AsyncClient, AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, session = api_client
    owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    member_tid = owner_tid + 1
    bot = AsyncMock()
    bot.send_message = AsyncMock()

    async def fake_resolve_bot(_bot):
        return bot, False

    monkeypatch.setattr(
        "app.services.membership_lifecycle.resolve_bot", fake_resolve_bot
    )

    owner, budget = await create_user_with_budget(session, telegram_id=owner_tid, role="owner")
    member = User(
        telegram_id=member_tid,
        family_budget_id=budget.id,
        role="member",
        language="ru",
    )
    session.add(member)
    await session.flush()
    await copy_seed_data(session, budget.id)
    personal_wallet = Wallet(
        family_budget_id=budget.id,
        name="Личный",
        currency="UZS",
        is_personal=True,
        owner_user_id=member.id,
    )
    session.add(personal_wallet)
    await session.flush()

    new_budget = await detach_member_to_own_budget(
        session,
        departing_user=member,
        old_budget=budget,
        reason="left",
        bot=None,
    )
    await session.flush()

    card_uzs = await session.scalar(
        select(Wallet).where(
            Wallet.family_budget_id == new_budget.id,
            Wallet.translation_key == "card_uzs",
            Wallet.is_deleted.is_(False),
        )
    )
    card_usd = await session.scalar(
        select(Wallet).where(
            Wallet.family_budget_id == new_budget.id,
            Wallet.translation_key == "card_usd",
            Wallet.is_deleted.is_(False),
        )
    )
    assert card_uzs is not None
    assert card_usd is not None

    demo_count = await session.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(
            Transaction.family_budget_id == new_budget.id,
            Transaction.is_demo.is_(True),
            Transaction.is_deleted.is_(False),
        )
    )
    assert demo_count == 21


@pytest.mark.anyio
async def test_demo_data_status_and_clear_owner_only(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    member_tid = owner_tid + 1
    owner, budget = await create_user_with_budget(session, telegram_id=owner_tid, role="owner")
    member = User(
        telegram_id=member_tid,
        family_budget_id=budget.id,
        role="member",
        language="ru",
    )
    session.add(member)
    await session.flush()
    await copy_seed_data(session, budget.id)
    await seed_demo_operations(session, budget.id, owner.id)

    wallet = await session.scalar(
        select(Wallet).where(
            Wallet.family_budget_id == budget.id,
            Wallet.translation_key == "card_uzs",
        )
    )
    income_cat = await session.scalar(
        select(IncomeCategory).where(
            IncomeCategory.family_budget_id == budget.id,
            IncomeCategory.translation_key == "salary",
        )
    )
    real_txn = Transaction(
        family_budget_id=budget.id,
        type="income",
        wallet_id=wallet.id,
        amount=50_000,
        income_category_id=income_cat.id,
        created_by_user_id=owner.id,
        transaction_date=datetime.now(UTC),
        is_demo=False,
    )
    session.add(real_txn)
    await session.flush()

    status_resp = await client.get(
        "/api/v1/demo-data/status",
        headers=auth_headers(owner_tid),
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["has_demo_data"] is True

    member_status = await client.get(
        "/api/v1/demo-data/status",
        headers=auth_headers(member_tid),
    )
    assert member_status.status_code == 403

    clear_resp = await client.delete(
        "/api/v1/demo-data",
        headers=auth_headers(owner_tid),
    )
    assert clear_resp.status_code == 200
    assert clear_resp.json()["cleared_count"] == 21

    after_status = await client.get(
        "/api/v1/demo-data/status",
        headers=auth_headers(owner_tid),
    )
    assert after_status.json()["has_demo_data"] is False

    await session.refresh(real_txn)
    assert real_txn.is_deleted is False

    member_clear = await client.delete(
        "/api/v1/demo-data",
        headers=auth_headers(member_tid),
    )
    assert member_clear.status_code == 403
