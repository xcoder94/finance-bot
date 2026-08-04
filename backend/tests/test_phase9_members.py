import socket
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine, get_session
from app.main import app
from app.models.family_budget import FamilyBudget
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.budget_seed import SEED_WALLETS
from app.services.entity_limits import LIMIT_MEMBERS, MEMBER_LIMIT
from app.services.member_texts import (
    departed_label,
    invite_already_member,
    invite_family_full_chat,
    invite_link_invalid,
    join_has_other_members,
    join_personal_wallet_cap,
    left_notice,
    removed_notice,
    welcome_invited,
)
from tests.auth_helpers import TEST_APP_PASS_SECRET, bearer_header_for_telegram_id
from tests.test_members import auth_headers, create_user_with_budget

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
        with patch("app.auth.deps.APP_PASS_SECRET", TEST_APP_PASS_SECRET):
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


def _mock_bot(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    bot = AsyncMock()
    bot.send_message = AsyncMock()

    async def fake_resolve_bot(b: AsyncMock | None) -> tuple[AsyncMock, bool]:
        return (bot if b is None else b), False

    monkeypatch.setattr(
        "app.services.membership_lifecycle.resolve_bot", fake_resolve_bot
    )
    monkeypatch.setattr("app.services.goal_notify.resolve_bot", fake_resolve_bot)
    return bot


async def _wallet_txn_totals(
    session: AsyncSession, wallet_id: uuid.UUID
) -> tuple[int, int]:
    txns = (
        await session.scalars(
            select(Transaction).where(
                Transaction.wallet_id == wallet_id,
                Transaction.is_deleted.is_(False),
            )
        )
    ).all()
    income = sum(t.amount for t in txns if t.type == "income")
    expense = sum(t.amount for t in txns if t.type == "expense")
    return income, expense


async def _count_wallets_in_budget(
    session: AsyncSession, budget_id: uuid.UUID
) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(Wallet)
            .where(
                Wallet.family_budget_id == budget_id,
                Wallet.is_deleted.is_(False),
            )
        )
        or 0
    )


def test_member_limit_constant_and_app_message():
    assert MEMBER_LIMIT == 4
    assert LIMIT_MEMBERS == "В семейном бюджете уже 4 участника — это предел."


def test_invite_and_join_texts_verbatim():
    assert "больше не действует" in invite_link_invalid()
    assert invite_family_full_chat() == (
        "В этом семейном бюджете уже 4 участника — это предел."
    )
    assert invite_already_member("Семья Юсуповых") == (
        "Вы уже участник бюджета «Семья Юсуповых»."
    )
    assert "пока в вашем бюджете есть участники" in join_has_other_members()
    assert "Сейчас у вас 12" in join_personal_wallet_cap(12)
    assert departed_label("Рустам") == "Рустам (бывший участник)"
    assert removed_notice("Семья Каримовых").startswith(
        "Вы больше не участник семейного бюджета «Семья Каримовых»."
    )
    assert left_notice("Семья Каримовых").startswith(
        "Вы вышли из бюджета «Семья Каримовых»."
    )
    assert "Вы присоединились к бюджету «Семья Юсуповых»." in welcome_invited(
        "Семья Юсуповых"
    )


pytestmark_lifecycle = [
    pytest.mark.skipif(not _db_available(), reason="DB not configured"),
    pytest.mark.anyio,
]


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_remove_member_personal_follows_shared_stays_aggregates_unchanged(
    api_client: tuple[AsyncClient, AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = api_client
    owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    member_tid = owner_tid + 1
    owner, budget = await create_user_with_budget(
        session,
        telegram_id=owner_tid,
        role="owner",
        first_name="Owner",
    )
    member, _ = await create_user_with_budget(
        session,
        telegram_id=member_tid,
        role="member",
        first_name="Bob",
        family_budget_id=budget.id,
    )
    budget.name = "Семья Каримовых"
    await session.flush()

    shared_wallet = Wallet(
        family_budget_id=budget.id,
        name="Shared",
        currency="UZS",
        is_personal=False,
    )
    personal_wallet = Wallet(
        family_budget_id=budget.id,
        name="Member Personal",
        currency="UZS",
        is_personal=True,
        owner_user_id=member.id,
    )
    session.add_all([shared_wallet, personal_wallet])
    await session.flush()

    session.add_all(
        [
            Transaction(
                family_budget_id=budget.id,
                type="income",
                wallet_id=shared_wallet.id,
                amount=500,
                created_by_user_id=member.id,
                transaction_date=datetime.now(UTC),
            ),
            Transaction(
                family_budget_id=budget.id,
                type="expense",
                wallet_id=shared_wallet.id,
                amount=200,
                created_by_user_id=member.id,
                transaction_date=datetime.now(UTC),
            ),
            Transaction(
                family_budget_id=budget.id,
                type="income",
                wallet_id=personal_wallet.id,
                amount=1000,
                created_by_user_id=member.id,
                transaction_date=datetime.now(UTC),
            ),
        ]
    )
    await session.flush()

    shared_income_before, shared_expense_before = await _wallet_txn_totals(
        session, shared_wallet.id
    )

    bot = _mock_bot(monkeypatch)

    delete_resp = await client.delete(
        f"/api/v1/members/{member.id}",
        headers=auth_headers(owner_tid),
    )
    assert delete_resp.status_code == 200

    await session.refresh(member)
    assert member.is_deleted is False
    assert member.role == "owner"
    assert member.family_budget_id != budget.id

    await session.refresh(personal_wallet)
    assert personal_wallet.family_budget_id == member.family_budget_id
    assert personal_wallet.is_personal is True
    assert personal_wallet.owner_user_id == member.id

    personal_txn = (
        await session.scalars(
            select(Transaction).where(
                Transaction.wallet_id == personal_wallet.id,
                Transaction.is_deleted.is_(False),
            )
        )
    ).one()
    assert personal_txn.family_budget_id == member.family_budget_id

    await session.refresh(shared_wallet)
    assert shared_wallet.family_budget_id == budget.id

    shared_income_after, shared_expense_after = await _wallet_txn_totals(
        session, shared_wallet.id
    )
    assert shared_income_after == shared_income_before
    assert shared_expense_after == shared_expense_before

    new_wallet_count = await _count_wallets_in_budget(session, member.family_budget_id)
    assert new_wallet_count == 1

    assert member.default_wallet_id == personal_wallet.id

    assert bot.send_message.await_count == 1
    notice_text = bot.send_message.await_args.args[1]
    assert notice_text.startswith(
        removed_notice("Семья Каримовых").split("\n")[0]
    )


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_remove_member_without_personal_seeds_four_and_default_card_uzs(
    api_client: tuple[AsyncClient, AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
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

    _mock_bot(monkeypatch)

    delete_resp = await client.delete(
        f"/api/v1/members/{member.id}",
        headers=auth_headers(owner_tid),
    )
    assert delete_resp.status_code == 200

    await session.refresh(member)
    new_wallet_count = await _count_wallets_in_budget(session, member.family_budget_id)
    assert new_wallet_count == len(SEED_WALLETS)

    card_uzs = await session.scalar(
        select(Wallet).where(
            Wallet.family_budget_id == member.family_budget_id,
            Wallet.name == "Карта сум",
            Wallet.is_deleted.is_(False),
        )
    )
    assert card_uzs is not None
    assert member.default_wallet_id == card_uzs.id


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_leave_uses_left_notice_first_line(
    api_client: tuple[AsyncClient, AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = api_client
    owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    member_tid = owner_tid + 1
    _, budget = await create_user_with_budget(session, telegram_id=owner_tid)
    member, _ = await create_user_with_budget(
        session,
        telegram_id=member_tid,
        role="member",
        family_budget_id=budget.id,
    )
    budget.name = "Семья Каримовых"
    await session.flush()

    bot = _mock_bot(monkeypatch)

    leave_resp = await client.post(
        "/api/v1/members/leave",
        headers=auth_headers(member_tid),
    )
    assert leave_resp.status_code == 200

    assert bot.send_message.await_count == 1
    notice_text = bot.send_message.await_args.args[1]
    assert notice_text.startswith(
        left_notice("Семья Каримовых").split("\n")[0]
    )

    await session.refresh(member)
    assert member.role == "owner"
    assert member.is_deleted is False


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_owner_cannot_leave(api_client: tuple[AsyncClient, AsyncSession]) -> None:
    client, session = api_client
    owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    await create_user_with_budget(session, telegram_id=owner_tid, role="owner")

    leave_resp = await client.post(
        "/api/v1/members/leave",
        headers=auth_headers(owner_tid),
    )
    assert leave_resp.status_code == 400
    assert leave_resp.json()["detail"] == "owner_cannot_leave"
