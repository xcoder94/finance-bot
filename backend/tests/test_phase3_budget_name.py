import uuid

import pytest
from sqlalchemy import inspect

from app.db import engine
from app.models.family_budget import FamilyBudget
from app.models.user import User
from app.models.wallet import Wallet
from tests.test_application_pass import (
    _build_init_data_for_telegram_id,
    _patched_api_client,
)
from tests.test_telegram_auth import (
    _db_available,
    _random_telegram_id,
    _reset_engine,
    rollback_session,
)


@pytest.mark.anyio
async def test_family_budget_name_column_exists():
    await _reset_engine()
    async with engine.connect() as conn:
        def check(sync_conn):
            insp = inspect(sync_conn)
            columns = {c["name"] for c in insp.get_columns("family_budgets")}
            assert "name" in columns

        await conn.run_sync(check)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL is not reachable on 127.0.0.1:5432")
@pytest.mark.anyio
async def test_me_returns_default_budget_name_and_solo_member_count() -> None:
    async with rollback_session() as session:
        telegram_id = _random_telegram_id()
        budget = FamilyBudget(invite_token=f"test-{uuid.uuid4()}")
        session.add(budget)
        await session.flush()
        session.add(
            User(
                telegram_id=telegram_id,
                family_budget_id=budget.id,
                role="owner",
                first_name="Owner",
                username="owner",
                language="ru",
            )
        )
        await session.flush()

        init_data = _build_init_data_for_telegram_id(telegram_id)
        async with _patched_api_client(session) as client:
            issue_response = await client.post(
                "/api/v1/auth/pass",
                headers={"Authorization": f"tma {init_data}"},
            )
            token = issue_response.json()["access_token"]
            me_response = await client.get(
                "/api/v1/me",
                headers={"Authorization": f"Bearer {token}"},
            )

    await _reset_engine()
    assert me_response.status_code == 200
    body = me_response.json()
    assert body["budget_name"] == "Семейный бюджет"
    assert body["member_count"] == 1
    assert body["default_wallet_id"] is None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL is not reachable on 127.0.0.1:5432")
@pytest.mark.anyio
async def test_me_member_count_excludes_deleted_users() -> None:
    async with rollback_session() as session:
        owner_tid = _random_telegram_id()
        member_tid = _random_telegram_id()
        budget = FamilyBudget(invite_token=f"test-{uuid.uuid4()}")
        session.add(budget)
        await session.flush()
        session.add(
            User(
                telegram_id=owner_tid,
                family_budget_id=budget.id,
                role="owner",
                language="ru",
            )
        )
        session.add(
            User(
                telegram_id=member_tid,
                family_budget_id=budget.id,
                role="member",
                language="ru",
            )
        )
        session.add(
            User(
                telegram_id=_random_telegram_id(),
                family_budget_id=budget.id,
                role="member",
                language="ru",
                is_deleted=True,
            )
        )
        await session.flush()

        init_data = _build_init_data_for_telegram_id(owner_tid)
        async with _patched_api_client(session) as client:
            issue_response = await client.post(
                "/api/v1/auth/pass",
                headers={"Authorization": f"tma {init_data}"},
            )
            token = issue_response.json()["access_token"]
            me_response = await client.get(
                "/api/v1/me",
                headers={"Authorization": f"Bearer {token}"},
            )

    await _reset_engine()
    assert me_response.status_code == 200
    assert me_response.json()["member_count"] == 2


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL is not reachable on 127.0.0.1:5432")
@pytest.mark.anyio
async def test_me_returns_default_wallet_id_when_set() -> None:
    async with rollback_session() as session:
        telegram_id = _random_telegram_id()
        budget = FamilyBudget(invite_token=f"test-{uuid.uuid4()}")
        session.add(budget)
        await session.flush()
        wallet = Wallet(
            family_budget_id=budget.id,
            name="Карта сум",
            currency="UZS",
        )
        session.add(wallet)
        await session.flush()
        session.add(
            User(
                telegram_id=telegram_id,
                family_budget_id=budget.id,
                role="owner",
                language="ru",
                default_wallet_id=wallet.id,
            )
        )
        await session.flush()

        init_data = _build_init_data_for_telegram_id(telegram_id)
        async with _patched_api_client(session) as client:
            issue_response = await client.post(
                "/api/v1/auth/pass",
                headers={"Authorization": f"tma {init_data}"},
            )
            token = issue_response.json()["access_token"]
            me_response = await client.get(
                "/api/v1/me",
                headers={"Authorization": f"Bearer {token}"},
            )

    await _reset_engine()
    assert me_response.status_code == 200
    assert me_response.json()["default_wallet_id"] == str(wallet.id)
