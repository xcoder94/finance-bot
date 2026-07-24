import json
import socket
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.telegram import sign_init_data
from app.db import engine, get_session
from app.main import app
from app.models.family_budget import FamilyBudget
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.invite import build_invite_link
from bot.onboarding import get_family_budget_by_invite_token

BOT_TOKEN = "5768337691:AAH5YkoiEuPk8-FZa32hStHTqXiLPtAEhx8"
TEST_BOT_USERNAME = "finance_test_bot"


def _db_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            return True
    except OSError:
        return False


async def _reset_engine() -> None:
    await engine.dispose()


@asynccontextmanager
async def rollback_session() -> AsyncIterator[AsyncSession]:
    await _reset_engine()
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await trans.rollback()
            await session.close()


def build_init_data(telegram_id: int) -> str:
    user_json = json.dumps(
        {"id": telegram_id, "first_name": "Test", "username": "testuser"},
        separators=(",", ":"),
    )
    fields = {
        "user": user_json,
        "auth_date": str(int(time.time())),
    }
    return sign_init_data(fields, BOT_TOKEN)


def auth_headers(telegram_id: int) -> dict[str, str]:
    return {"Authorization": f"tma {build_init_data(telegram_id)}"}


async def create_user_with_budget(
    session: AsyncSession,
    *,
    telegram_id: int,
    role: str = "owner",
    first_name: str | None = "Owner",
    username: str | None = "owner_user",
    invite_token: str | None = None,
    family_budget_id: uuid.UUID | None = None,
) -> tuple[User, FamilyBudget]:
    if family_budget_id is None:
        budget = FamilyBudget(invite_token=invite_token or f"test-{uuid.uuid4()}")
        session.add(budget)
        await session.flush()
    else:
        budget = await session.get(FamilyBudget, family_budget_id)
        assert budget is not None

    user = User(
        telegram_id=telegram_id,
        family_budget_id=budget.id,
        role=role,
        first_name=first_name,
        username=username,
        language="ru",
    )
    session.add(user)
    await session.flush()
    return user, budget


@pytest.fixture
async def api_client() -> AsyncIterator[tuple[AsyncClient, AsyncSession]]:
    await _reset_engine()
    conn = await engine.connect()
    trans = await conn.begin()
    session = AsyncSession(
        bind=conn,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_get_session

    with patch("app.main.verify_postgres_connection", new=AsyncMock()):
        with patch("app.auth.telegram.BOT_TOKEN", BOT_TOKEN):
            with patch(
                "app.api.v1.members.get_bot_username",
                new=AsyncMock(return_value=TEST_BOT_USERNAME),
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    yield client, session

    await trans.rollback()
    await session.close()
    await conn.close()
    await _reset_engine()
    app.dependency_overrides.clear()


pytestmark = [
    pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available"),
    pytest.mark.anyio,
]


class TestListMembers:
    async def test_owner_and_member_can_list_family_members(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        member_tid = owner_tid + 1
        owner, budget = await create_user_with_budget(
            session,
            telegram_id=owner_tid,
            role="owner",
            first_name="Alice",
            username="alice",
        )
        member, _ = await create_user_with_budget(
            session,
            telegram_id=member_tid,
            role="member",
            first_name="Bob",
            username="bob",
            family_budget_id=budget.id,
        )

        owner_resp = await client.get("/api/v1/members", headers=auth_headers(owner_tid))
        assert owner_resp.status_code == 200
        owner_members = owner_resp.json()
        assert len(owner_members) == 2
        by_id = {row["id"]: row for row in owner_members}
        assert by_id[str(owner.id)] == {
            "id": str(owner.id),
            "first_name": "Alice",
            "username": "alice",
            "role": "owner",
        }
        assert by_id[str(member.id)] == {
            "id": str(member.id),
            "first_name": "Bob",
            "username": "bob",
            "role": "member",
        }

        member_resp = await client.get("/api/v1/members", headers=auth_headers(member_tid))
        assert member_resp.status_code == 200
        assert len(member_resp.json()) == 2

    async def test_list_members_excludes_soft_deleted(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        member_tid = owner_tid + 1
        owner, budget = await create_user_with_budget(session, telegram_id=owner_tid)
        removed, _ = await create_user_with_budget(
            session,
            telegram_id=member_tid,
            role="member",
            family_budget_id=budget.id,
        )
        removed.is_deleted = True
        removed.deleted_at = datetime.now(UTC)
        await session.flush()

        response = await client.get("/api/v1/members", headers=auth_headers(owner_tid))
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == str(owner.id)


class TestInviteLink:
    async def test_get_invite_link_matches_current_token(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        invite_token = f"invite-token-{uuid.uuid4()}"
        await create_user_with_budget(
            session,
            telegram_id=owner_tid,
            invite_token=invite_token,
        )

        response = await client.get(
            "/api/v1/members/invite-link",
            headers=auth_headers(owner_tid),
        )
        assert response.status_code == 200
        assert response.json()["invite_link"] == build_invite_link(
            TEST_BOT_USERNAME,
            invite_token,
        )

    async def test_regenerate_changes_token_and_invalidates_old_link(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        old_token = f"old-token-{uuid.uuid4()}"
        _, budget = await create_user_with_budget(
            session,
            telegram_id=owner_tid,
            invite_token=old_token,
        )
        headers = auth_headers(owner_tid)

        old_link_resp = await client.get("/api/v1/members/invite-link", headers=headers)
        old_link = old_link_resp.json()["invite_link"]

        regenerate_resp = await client.post(
            "/api/v1/members/invite-link/regenerate",
            headers=headers,
        )
        assert regenerate_resp.status_code == 200
        new_link = regenerate_resp.json()["invite_link"]
        assert new_link != old_link

        get_after = await client.get("/api/v1/members/invite-link", headers=headers)
        assert get_after.json()["invite_link"] == new_link

        await session.refresh(budget)
        assert budget.invite_token != old_token
        assert new_link == build_invite_link(TEST_BOT_USERNAME, budget.invite_token)

        assert await get_family_budget_by_invite_token(session, old_token) is None
        assert await get_family_budget_by_invite_token(session, budget.invite_token) is not None


class TestDeleteMember:
    async def test_owner_soft_deletes_member_and_transactions_unchanged(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        member_tid = owner_tid + 1
        owner, budget = await create_user_with_budget(session, telegram_id=owner_tid)
        member, _ = await create_user_with_budget(
            session,
            telegram_id=member_tid,
            role="member",
            first_name="Bob",
            family_budget_id=budget.id,
        )
        wallet = Wallet(family_budget_id=budget.id, name="Main", currency="UZS")
        session.add(wallet)
        await session.flush()
        txn = Transaction(
            family_budget_id=budget.id,
            type="income",
            wallet_id=wallet.id,
            amount=100,
            created_by_user_id=member.id,
            transaction_date=datetime.now(UTC),
        )
        session.add(txn)
        await session.flush()
        headers = auth_headers(owner_tid)

        delete_resp = await client.delete(f"/api/v1/members/{member.id}", headers=headers)
        assert delete_resp.status_code == 200
        assert delete_resp.json() == {
            "id": str(member.id),
            "first_name": "Bob",
            "role": "member",
        }

        list_resp = await client.get("/api/v1/members", headers=headers)
        assert len(list_resp.json()) == 1
        assert list_resp.json()[0]["id"] == str(owner.id)

        await session.refresh(txn)
        assert txn.created_by_user_id == member.id
        assert txn.is_deleted is False

        await session.refresh(budget)
        assert budget.invite_token is not None

    async def test_delete_self_returns_400(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        owner, _ = await create_user_with_budget(session, telegram_id=owner_tid)

        response = await client.delete(
            f"/api/v1/members/{owner.id}",
            headers=auth_headers(owner_tid),
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "cannot_remove_self"

    async def test_delete_already_removed_or_missing_returns_404(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        member_tid = owner_tid + 1
        owner, budget = await create_user_with_budget(session, telegram_id=owner_tid)
        member, _ = await create_user_with_budget(
            session,
            telegram_id=member_tid,
            role="member",
            family_budget_id=budget.id,
        )
        headers = auth_headers(owner_tid)

        first_delete = await client.delete(f"/api/v1/members/{member.id}", headers=headers)
        assert first_delete.status_code == 200

        second_delete = await client.delete(f"/api/v1/members/{member.id}", headers=headers)
        assert second_delete.status_code == 404

        missing_delete = await client.delete(
            f"/api/v1/members/{uuid.uuid4()}",
            headers=headers,
        )
        assert missing_delete.status_code == 404


class TestMemberForbiddenWrites:
    async def test_member_gets_403_on_owner_only_endpoints(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        member_tid = owner_tid + 1
        owner, budget = await create_user_with_budget(session, telegram_id=owner_tid)
        member, _ = await create_user_with_budget(
            session,
            telegram_id=member_tid,
            role="member",
            family_budget_id=budget.id,
        )
        headers = auth_headers(member_tid)

        assert (await client.get("/api/v1/members", headers=headers)).status_code == 200
        assert (
            await client.get("/api/v1/members/invite-link", headers=headers)
        ).status_code == 403
        assert (
            await client.post("/api/v1/members/invite-link/regenerate", headers=headers)
        ).status_code == 403
        assert (
            await client.delete(f"/api/v1/members/{owner.id}", headers=headers)
        ).status_code == 403


class TestCrossFamilyDelete:
    async def test_cross_family_member_delete_returns_404(
        self, api_client: tuple[AsyncClient, AsyncSession]
    ) -> None:
        client, session = api_client
        owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        other_tid = owner_tid + 1
        await create_user_with_budget(session, telegram_id=owner_tid, role="owner")
        _, other_budget = await create_user_with_budget(session, telegram_id=other_tid, role="owner")
        other_member_tid = other_tid + 1
        other_member, _ = await create_user_with_budget(
            session,
            telegram_id=other_member_tid,
            role="member",
            family_budget_id=other_budget.id,
        )

        response = await client.delete(
            f"/api/v1/members/{other_member.id}",
            headers=auth_headers(owner_tid),
        )
        assert response.status_code == 404
