import socket
import uuid
from datetime import UTC, date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from app.models.transaction import Transaction
from app.models.transaction_change_log import TransactionChangeLog
from app.models.user import User
from app.models.wallet import Wallet
from app.services.change_log_format import (
    FIELD_AMOUNT,
    FIELD_CATEGORY,
    FIELD_COMMENT,
    FIELD_WALLET,
    change_line,
    creation_line,
)
from tests.test_transactions import (
    api_client,
    auth_headers,
    create_user_with_budget,
    seed_expense_fixtures,
    txn_payload,
)

TASHKENT = ZoneInfo("Asia/Tashkent")
EDIT_DATE = date(2026, 8, 2)
CREATION_DATE = date(2026, 8, 1)


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


def test_change_log_model_tablename():
    assert TransactionChangeLog.__tablename__ == "transaction_change_logs"


async def _create_owner_and_member(
    session: AsyncSession,
    *,
    owner_first_name: str = "Рустам",
    member_first_name: str = "Дилноза",
) -> tuple[int, int, User, User, object]:
    owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    member_tid = owner_tid + 1
    owner, budget = await create_user_with_budget(
        session, telegram_id=owner_tid, role="owner"
    )
    owner.first_name = owner_first_name
    member = User(
        telegram_id=member_tid,
        family_budget_id=budget.id,
        role="member",
        language="ru",
        first_name=member_first_name,
    )
    session.add(member)
    await session.flush()
    return owner_tid, member_tid, owner, member, budget


async def _seed_shared_expense(
    session: AsyncSession,
    budget,
    owner: User,
    *,
    amount: int = 20_000,
    comment: str | None = None,
    created_at: datetime | None = None,
) -> tuple[Transaction, Wallet, ExpenseCategory, ExpenseCategory]:
    wallet, top, sub = await seed_expense_fixtures(session, budget)
    txn = Transaction(
        family_budget_id=budget.id,
        type="expense",
        wallet_id=wallet.id,
        amount=amount,
        expense_category_id=sub.id,
        comment=comment,
        created_by_user_id=owner.id,
        transaction_date=datetime(2026, 8, 1, 10, 0, tzinfo=TASHKENT),
        created_at=created_at or datetime(2026, 8, 1, 5, 0, tzinfo=UTC),
    )
    session.add(txn)
    await session.flush()
    return txn, wallet, top, sub


@patch("app.services.change_log._tashkent_today", return_value=EDIT_DATE)
async def test_member_b_edits_shared_amount_logs_creation_and_change(
    mock_today: object,
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid, member_tid, owner, _member, budget = await _create_owner_and_member(session)
    txn, wallet, _top, sub = await _seed_shared_expense(session, budget, owner)

    member_headers = auth_headers(member_tid)
    patch_resp = await client.patch(
        f"/api/v1/transactions/{txn.id}",
        headers=member_headers,
        json=txn_payload(
            wallet_id=str(wallet.id),
            expense_category_id=str(sub.id),
            amount=200_000,
            transaction_date=txn.transaction_date.isoformat(),
        ),
    )
    assert patch_resp.status_code == 200, patch_resp.text

    get_resp = await client.get(
        f"/api/v1/transactions/{txn.id}",
        headers=auth_headers(owner_tid),
    )
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["created_by_user_id"] == str(owner.id)
    assert data["changes"] == [
        creation_line(created_on=CREATION_DATE, creator_name="Рустам"),
        change_line(
            edited_on=EDIT_DATE,
            editor_name="Дилноза",
            field_label=FIELD_AMOUNT,
            old_value="20 000",
            new_value="200 000",
        ),
    ]


@patch("app.services.change_log._tashkent_today", return_value=EDIT_DATE)
async def test_multi_field_edit_three_lines_one_date(
    mock_today: object,
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid, _member_tid, owner, _member, budget = await _create_owner_and_member(session)
    txn, wallet, _top, sub = await _seed_shared_expense(
        session, budget, owner, amount=10_000, comment="old"
    )
    taxi = ExpenseCategory(family_budget_id=budget.id, name="Такси", parent_id=_top.id)
    session.add(taxi)
    await session.flush()

    patch_resp = await client.patch(
        f"/api/v1/transactions/{txn.id}",
        headers=auth_headers(owner_tid),
        json=txn_payload(
            wallet_id=str(wallet.id),
            expense_category_id=str(taxi.id),
            amount=15_000,
            comment="new",
            transaction_date=txn.transaction_date.isoformat(),
        ),
    )
    assert patch_resp.status_code == 200, patch_resp.text

    changes = patch_resp.json()["changes"]
    assert len(changes) == 4
    assert changes[0] == creation_line(created_on=CREATION_DATE, creator_name="Рустам")
    change_lines = changes[1:]
    assert len(change_lines) == 3
    prefix = "2 августа · Рустам:"
    assert all(line.startswith(prefix) for line in change_lines)
    assert any(FIELD_AMOUNT in line for line in change_lines)
    assert any(FIELD_CATEGORY in line for line in change_lines)
    assert any(FIELD_COMMENT in line for line in change_lines)


async def test_never_edited_changes_empty(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid, _member_tid, owner, _member, budget = await _create_owner_and_member(session)
    txn, wallet, _top, sub = await _seed_shared_expense(session, budget, owner)

    get_resp = await client.get(
        f"/api/v1/transactions/{txn.id}",
        headers=auth_headers(owner_tid),
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["changes"] == []


@patch("app.services.change_log._tashkent_today", return_value=EDIT_DATE)
async def test_wallet_rename_does_not_rewrite_old_log(
    mock_today: object,
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid, _member_tid, owner, _member, budget = await _create_owner_and_member(session)
    wallet_a = Wallet(family_budget_id=budget.id, name="Наличные", currency="UZS")
    wallet_b = Wallet(family_budget_id=budget.id, name="Карта", currency="UZS")
    top = ExpenseCategory(family_budget_id=budget.id, name="Food")
    session.add_all([wallet_a, wallet_b, top])
    await session.flush()
    sub = ExpenseCategory(family_budget_id=budget.id, name="Groceries", parent_id=top.id)
    session.add(sub)
    await session.flush()
    txn = Transaction(
        family_budget_id=budget.id,
        type="expense",
        wallet_id=wallet_a.id,
        amount=5_000,
        expense_category_id=sub.id,
        created_by_user_id=owner.id,
        transaction_date=datetime(2026, 8, 1, 10, 0, tzinfo=TASHKENT),
        created_at=datetime(2026, 8, 1, 5, 0, tzinfo=UTC),
    )
    session.add(txn)
    await session.flush()

    patch_resp = await client.patch(
        f"/api/v1/transactions/{txn.id}",
        headers=auth_headers(owner_tid),
        json=txn_payload(
            wallet_id=str(wallet_b.id),
            expense_category_id=str(sub.id),
            amount=5_000,
            transaction_date=txn.transaction_date.isoformat(),
        ),
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert any("Наличные" in line and FIELD_WALLET in line for line in patch_resp.json()["changes"])

    wallet_a.name = "Переименовано"
    await session.flush()

    get_resp = await client.get(
        f"/api/v1/transactions/{txn.id}",
        headers=auth_headers(owner_tid),
    )
    assert get_resp.status_code == 200
    wallet_line = next(
        line for line in get_resp.json()["changes"] if FIELD_WALLET in line
    )
    assert "Наличные" in wallet_line
    assert "Переименовано" not in wallet_line
    assert "Карта" in wallet_line


async def test_delete_not_logged_and_get_404(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid, _member_tid, owner, _member, budget = await _create_owner_and_member(session)
    txn, wallet, _top, sub = await _seed_shared_expense(session, budget, owner)

    delete_resp = await client.delete(
        f"/api/v1/transactions/{txn.id}",
        headers=auth_headers(owner_tid),
    )
    assert delete_resp.status_code == 200

    get_resp = await client.get(
        f"/api/v1/transactions/{txn.id}",
        headers=auth_headers(owner_tid),
    )
    assert get_resp.status_code == 404


async def test_personal_op_hidden_from_other_member(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    owner_tid, member_tid, owner, member, budget = await _create_owner_and_member(session)
    personal = Wallet(
        family_budget_id=budget.id,
        name="Owner Personal",
        currency="UZS",
        is_personal=True,
        owner_user_id=owner.id,
    )
    top = ExpenseCategory(family_budget_id=budget.id, name="Food")
    session.add_all([personal, top])
    await session.flush()
    sub = ExpenseCategory(family_budget_id=budget.id, name="Groceries", parent_id=top.id)
    session.add(sub)
    await session.flush()
    txn = Transaction(
        family_budget_id=budget.id,
        type="expense",
        wallet_id=personal.id,
        amount=1_000,
        expense_category_id=sub.id,
        created_by_user_id=owner.id,
        transaction_date=datetime.now(UTC),
    )
    session.add(txn)
    await session.flush()

    member_headers = auth_headers(member_tid)
    assert (
        await client.get(f"/api/v1/transactions/{txn.id}", headers=member_headers)
    ).status_code == 404
    assert (
        await client.patch(
            f"/api/v1/transactions/{txn.id}",
            headers=member_headers,
            json=txn_payload(
                wallet_id=str(personal.id),
                expense_category_id=str(sub.id),
                amount=2_000,
            ),
        )
    ).status_code == 404
