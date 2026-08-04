import socket
import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from app.models.transaction import Transaction
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


SELECTED_MONTH_START = datetime(2026, 3, 1, tzinfo=UTC)
SELECTED_MONTH_END = datetime(2026, 3, 31, 23, 59, 59, tzinfo=UTC)
SELECTED_MONTH_DATE = datetime(2026, 3, 10, tzinfo=UTC)
MEMBER_PERSONAL_EXPENSE = 777
SHARED_EXPENSE = 1_000


async def _seed_member_personal_expense(
    session: AsyncSession,
    budget_id: uuid.UUID,
    member: User,
    amount: int = MEMBER_PERSONAL_EXPENSE,
) -> tuple[Wallet, Transaction]:
    personal = Wallet(
        family_budget_id=budget_id,
        name="Member Personal",
        currency="UZS",
        is_personal=True,
        owner_user_id=member.id,
    )
    food = ExpenseCategory(family_budget_id=budget_id, name="Food")
    session.add_all([personal, food])
    await session.flush()
    sub = ExpenseCategory(family_budget_id=budget_id, name="Groceries", parent_id=food.id)
    session.add(sub)
    await session.flush()
    txn = Transaction(
        family_budget_id=budget_id,
        type="expense",
        wallet_id=personal.id,
        amount=amount,
        expense_category_id=sub.id,
        created_by_user_id=member.id,
        transaction_date=SELECTED_MONTH_DATE,
    )
    session.add(txn)
    await session.flush()
    return personal, txn


async def test_history_hides_others_personal_expense(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid, member_tid, owner, member = await _create_owner_and_member(session)
    shared = Wallet(
        family_budget_id=owner.family_budget_id,
        name="Shared",
        currency="UZS",
        is_personal=False,
    )
    session.add(shared)
    await session.flush()
    _, txn = await _seed_member_personal_expense(session, owner.family_budget_id, member)
    history_params = {
        "date_from": SELECTED_MONTH_START.isoformat(),
        "date_to": SELECTED_MONTH_END.isoformat(),
    }

    owner_resp = await client.get(
        "/api/v1/transactions/history",
        headers=auth_headers(owner_tid),
        params=history_params,
    )
    assert owner_resp.status_code == 200
    owner_amounts = {item["amount"] for item in owner_resp.json()["items"]}
    assert MEMBER_PERSONAL_EXPENSE not in owner_amounts

    member_resp = await client.get(
        "/api/v1/transactions/history",
        headers=auth_headers(member_tid),
        params=history_params,
    )
    assert member_resp.status_code == 200
    member_amounts = {item["amount"] for item in member_resp.json()["items"]}
    assert MEMBER_PERSONAL_EXPENSE in member_amounts
    assert str(txn.id) in {item["id"] for item in member_resp.json()["items"]}


async def test_get_transaction_others_personal_404(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid, member_tid, owner, member = await _create_owner_and_member(session)
    _, txn = await _seed_member_personal_expense(session, owner.family_budget_id, member)

    owner_resp = await client.get(
        f"/api/v1/transactions/{txn.id}",
        headers=auth_headers(owner_tid),
    )
    assert owner_resp.status_code == 404

    member_resp = await client.get(
        f"/api/v1/transactions/{txn.id}",
        headers=auth_headers(member_tid),
    )
    assert member_resp.status_code == 200
    assert member_resp.json()["amount"] == MEMBER_PERSONAL_EXPENSE


async def test_member_cannot_post_expense_on_others_personal(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid, member_tid, owner, member = await _create_owner_and_member(session)
    personal, _ = await _seed_member_personal_expense(session, owner.family_budget_id, member)
    food = ExpenseCategory(family_budget_id=owner.family_budget_id, name="Food2")
    session.add(food)
    await session.flush()
    sub = ExpenseCategory(
        family_budget_id=owner.family_budget_id, name="Snacks", parent_id=food.id
    )
    session.add(sub)
    await session.flush()

    response = await client.post(
        "/api/v1/transactions/expense",
        headers=auth_headers(owner_tid),
        json={
            "transaction_date": SELECTED_MONTH_DATE.isoformat(),
            "amount": 100,
            "wallet_id": str(personal.id),
            "expense_category_id": str(sub.id),
        },
    )
    assert response.status_code == 404


async def test_analytics_summary_excludes_personal(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid, _, owner, member = await _create_owner_and_member(session)
    shared = Wallet(
        family_budget_id=owner.family_budget_id,
        name="Shared",
        currency="UZS",
        is_personal=False,
    )
    food = ExpenseCategory(family_budget_id=owner.family_budget_id, name="Food")
    session.add_all([shared, food])
    await session.flush()
    sub = ExpenseCategory(
        family_budget_id=owner.family_budget_id, name="Groceries", parent_id=food.id
    )
    session.add(sub)
    await session.flush()
    session.add(
        Transaction(
            family_budget_id=owner.family_budget_id,
            type="expense",
            wallet_id=shared.id,
            amount=SHARED_EXPENSE,
            expense_category_id=sub.id,
            created_by_user_id=owner.id,
            transaction_date=SELECTED_MONTH_DATE,
        )
    )
    await session.flush()
    await _seed_member_personal_expense(session, owner.family_budget_id, member)

    resp = await client.get(
        "/api/v1/analytics/summary",
        headers=auth_headers(owner_tid),
        params={
            "date_from": SELECTED_MONTH_START.isoformat(),
            "date_to": SELECTED_MONTH_END.isoformat(),
        },
    )
    assert resp.status_code == 200
    by_currency = {row["currency"]: row for row in resp.json()["by_currency"]}
    assert by_currency["UZS"]["expense"] == SHARED_EXPENSE


def _summary_params() -> dict[str, str]:
    return {
        "date_from": SELECTED_MONTH_START.isoformat(),
        "date_to": SELECTED_MONTH_END.isoformat(),
    }


async def test_personal_summary_includes_holder_expense(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid, member_tid, owner, member = await _create_owner_and_member(session)
    await _seed_member_personal_expense(session, owner.family_budget_id, member)

    resp = await client.get(
        "/api/v1/analytics/personal-summary",
        headers=auth_headers(member_tid),
        params=_summary_params(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "UZS" in body["currencies_with_wallets"]
    by_currency = {row["currency"]: row for row in body["by_currency"]}
    assert by_currency["UZS"]["expense"] == MEMBER_PERSONAL_EXPENSE
    assert by_currency["UZS"]["income"] == 0


async def test_personal_currencies_with_wallet_no_ops(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    _, member_tid, _, member = await _create_owner_and_member(session)
    session.add(
        Wallet(
            family_budget_id=member.family_budget_id,
            name="Empty Personal",
            currency="UZS",
            is_personal=True,
            owner_user_id=member.id,
        )
    )
    await session.flush()

    summary_resp = await client.get(
        "/api/v1/analytics/personal-summary",
        headers=auth_headers(member_tid),
        params=_summary_params(),
    )
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["currencies_with_wallets"] == ["UZS"]
    by_currency = {row["currency"]: row for row in summary["by_currency"]}
    assert by_currency["UZS"]["income"] == 0
    assert by_currency["UZS"]["expense"] == 0

    balances_resp = await client.get(
        "/api/v1/analytics/personal-wallet-balances",
        headers=auth_headers(member_tid),
    )
    assert balances_resp.status_code == 200
    balances = balances_resp.json()
    assert balances["currencies_with_wallets"] == ["UZS"]
    balance_by_currency = {row["currency"]: row["balance"] for row in balances["balances"]}
    assert balance_by_currency["UZS"] == 0


async def test_personal_not_visible_to_owner(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid, member_tid, owner, member = await _create_owner_and_member(session)
    await _seed_member_personal_expense(session, owner.family_budget_id, member)

    summary_resp = await client.get(
        "/api/v1/analytics/personal-summary",
        headers=auth_headers(owner_tid),
        params=_summary_params(),
    )
    assert summary_resp.status_code == 200
    assert summary_resp.json()["currencies_with_wallets"] == []
    assert summary_resp.json()["by_currency"] == []

    balances_resp = await client.get(
        "/api/v1/analytics/personal-wallet-balances",
        headers=auth_headers(owner_tid),
    )
    assert balances_resp.status_code == 200
    balances = balances_resp.json()
    assert balances["currencies_with_wallets"] == []
    assert all(row["balance"] == 0 for row in balances["balances"])


async def test_shared_summary_unaffected(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid, _, owner, member = await _create_owner_and_member(session)
    shared = Wallet(
        family_budget_id=owner.family_budget_id,
        name="Shared",
        currency="UZS",
        is_personal=False,
    )
    food = ExpenseCategory(family_budget_id=owner.family_budget_id, name="Food")
    session.add_all([shared, food])
    await session.flush()
    sub = ExpenseCategory(
        family_budget_id=owner.family_budget_id, name="Groceries", parent_id=food.id
    )
    session.add(sub)
    await session.flush()
    session.add(
        Transaction(
            family_budget_id=owner.family_budget_id,
            type="expense",
            wallet_id=shared.id,
            amount=SHARED_EXPENSE,
            expense_category_id=sub.id,
            created_by_user_id=owner.id,
            transaction_date=SELECTED_MONTH_DATE,
        )
    )
    await session.flush()
    await _seed_member_personal_expense(session, owner.family_budget_id, member)

    shared_resp = await client.get(
        "/api/v1/analytics/summary",
        headers=auth_headers(owner_tid),
        params=_summary_params(),
    )
    assert shared_resp.status_code == 200
    shared_by_currency = {
        row["currency"]: row for row in shared_resp.json()["by_currency"]
    }
    assert shared_by_currency["UZS"]["expense"] == SHARED_EXPENSE

    balances_resp = await client.get(
        "/api/v1/analytics/wallet-balances",
        headers=auth_headers(owner_tid),
    )
    assert balances_resp.status_code == 200
    shared_balances = {
        row["currency"]: row["balance"] for row in balances_resp.json()["balances"]
    }
    assert shared_balances["UZS"] == -SHARED_EXPENSE
