import socket
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.wallet import Wallet
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


pytestmark = [
    pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available"),
    pytest.mark.anyio,
]


async def test_list_hides_other_members_personal_wallet(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
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

    shared = Wallet(
        family_budget_id=budget.id,
        name="Shared",
        currency="UZS",
        is_personal=False,
    )
    member_personal = Wallet(
        family_budget_id=budget.id,
        name="Member Personal",
        currency="UZS",
        is_personal=True,
        owner_user_id=member.id,
    )
    session.add_all([shared, member_personal])
    await session.flush()

    owner_headers = auth_headers(owner_tid)
    owner_resp = await client.get("/api/v1/wallets", headers=owner_headers)
    assert owner_resp.status_code == 200
    owner_ids = {w["id"] for w in owner_resp.json()}
    assert str(shared.id) in owner_ids
    assert str(member_personal.id) not in owner_ids

    member_headers = auth_headers(member_tid)
    member_resp = await client.get("/api/v1/wallets", headers=member_headers)
    assert member_resp.status_code == 200
    member_wallets = {w["id"]: w for w in member_resp.json()}
    assert str(shared.id) in member_wallets
    assert str(member_personal.id) in member_wallets
    assert member_wallets[str(member_personal.id)]["is_personal"] is True


async def test_patch_me_rejects_others_personal_as_default(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    member_tid = owner_tid + 1
    _, budget = await create_user_with_budget(session, telegram_id=owner_tid, role="owner")
    member = User(
        telegram_id=member_tid,
        family_budget_id=budget.id,
        role="member",
        language="ru",
    )
    session.add(member)
    await session.flush()

    member_personal = Wallet(
        family_budget_id=budget.id,
        name="Member Personal",
        currency="UZS",
        is_personal=True,
        owner_user_id=member.id,
    )
    session.add(member_personal)
    await session.flush()

    response = await client.patch(
        "/api/v1/me",
        headers=auth_headers(owner_tid),
        json={"default_wallet_id": str(member_personal.id)},
    )
    assert response.status_code == 404
