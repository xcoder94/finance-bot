import socket
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.wallet import Wallet
from app.services.entity_limits import LIMIT_PERSONAL_WALLETS
from tests.test_wallets_categories import (
    api_client,
    auth_headers,
    create_user_with_budget,
)


async def _create_owner_and_member(
    session: AsyncSession,
) -> tuple[int, int, User, User]:
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
    return owner_tid, member_tid, owner, member


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


async def test_member_creates_personal_wallet(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid, member_tid, owner, member = await _create_owner_and_member(session)
    session.add(
        Wallet(
            family_budget_id=owner.family_budget_id,
            name="Shared",
            currency="UZS",
            is_personal=False,
        )
    )
    await session.flush()

    response = await client.post(
        "/api/v1/wallets",
        headers=auth_headers(member_tid),
        json={"name": "My Personal", "currency": "UZS", "is_personal": True},
    )
    assert response.status_code == 201
    created = response.json()
    assert created["name"] == "My Personal"
    assert created["currency"] == "UZS"
    assert created["is_personal"] is True

    member_resp = await client.get("/api/v1/wallets", headers=auth_headers(member_tid))
    member_ids = {w["id"] for w in member_resp.json()}
    assert created["id"] in member_ids

    owner_resp = await client.get("/api/v1/wallets", headers=auth_headers(owner_tid))
    owner_ids = {w["id"] for w in owner_resp.json()}
    assert created["id"] not in owner_ids


async def test_member_cannot_create_shared(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    _, member_tid, _, member = await _create_owner_and_member(session)

    response = await client.post(
        "/api/v1/wallets",
        headers=auth_headers(member_tid),
        json={"name": "Shared Attempt", "currency": "UZS", "is_personal": False},
    )
    assert response.status_code == 403


async def test_personal_6th_returns_exact_19_1(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    _, member_tid, _, member = await _create_owner_and_member(session)
    headers = auth_headers(member_tid)

    for i in range(5):
        session.add(
            Wallet(
                family_budget_id=member.family_budget_id,
                name=f"Personal {i}",
                currency="UZS",
                is_personal=True,
                owner_user_id=member.id,
            )
        )
    await session.flush()

    response = await client.post(
        "/api/v1/wallets",
        headers=headers,
        json={"name": "Sixth", "currency": "UZS", "is_personal": True},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == LIMIT_PERSONAL_WALLETS


async def test_delete_personal_frees_slot(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    _, member_tid, _, member = await _create_owner_and_member(session)
    headers = auth_headers(member_tid)

    wallets = [
        Wallet(
            family_budget_id=member.family_budget_id,
            name=f"Personal {i}",
            currency="UZS",
            is_personal=True,
            owner_user_id=member.id,
        )
        for i in range(5)
    ]
    session.add_all(wallets)
    await session.flush()

    delete_resp = await client.delete(
        f"/api/v1/wallets/{wallets[0].id}",
        headers=headers,
    )
    assert delete_resp.status_code == 200

    create_resp = await client.post(
        "/api/v1/wallets",
        headers=headers,
        json={"name": "Replacement", "currency": "UZS", "is_personal": True},
    )
    assert create_resp.status_code == 201


async def test_holder_renames_personal(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    _, member_tid, _, member = await _create_owner_and_member(session)
    personal = Wallet(
        family_budget_id=member.family_budget_id,
        name="Old Name",
        currency="UZS",
        is_personal=True,
        owner_user_id=member.id,
    )
    session.add(personal)
    await session.flush()

    response = await client.patch(
        f"/api/v1/wallets/{personal.id}",
        headers=auth_headers(member_tid),
        json={"name": "New Name"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


async def test_owner_cannot_patch_members_personal(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid, _, _, member = await _create_owner_and_member(session)
    personal = Wallet(
        family_budget_id=member.family_budget_id,
        name="Member Personal",
        currency="UZS",
        is_personal=True,
        owner_user_id=member.id,
    )
    session.add(personal)
    await session.flush()

    response = await client.patch(
        f"/api/v1/wallets/{personal.id}",
        headers=auth_headers(owner_tid),
        json={"name": "Hacked"},
    )
    assert response.status_code == 404


async def test_owner_cannot_delete_members_personal(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid, _, _, member = await _create_owner_and_member(session)
    personal = Wallet(
        family_budget_id=member.family_budget_id,
        name="Member Personal",
        currency="UZS",
        is_personal=True,
        owner_user_id=member.id,
    )
    session.add(personal)
    await session.flush()

    response = await client.delete(
        f"/api/v1/wallets/{personal.id}",
        headers=auth_headers(owner_tid),
    )
    assert response.status_code == 404


async def test_member_cannot_patch_shared(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    _, member_tid, owner, member = await _create_owner_and_member(session)
    shared = Wallet(
        family_budget_id=owner.family_budget_id,
        name="Shared",
        currency="UZS",
        is_personal=False,
    )
    session.add(shared)
    await session.flush()

    response = await client.patch(
        f"/api/v1/wallets/{shared.id}",
        headers=auth_headers(member_tid),
        json={"name": "Nope"},
    )
    assert response.status_code == 403
