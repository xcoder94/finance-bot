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
from app.models.expense_category import ExpenseCategory
from app.models.goal import Goal
from app.models.ownership_transfer import OwnershipTransfer
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.budget_seed import SEED_WALLETS, copy_seed_data
from app.services.entity_limits import LIMIT_MEMBERS, MEMBER_LIMIT, PERSONAL_WALLET_LIMIT
from app.services.member_texts import (
    departed_label,
    invite_already_member,
    invite_family_full_chat,
    invite_link_invalid,
    join_confirm_prompt,
    join_has_other_members,
    join_personal_wallet_cap,
    left_notice,
    removed_notice,
    transfer_accepted_to_former,
    transfer_accepted_to_others,
    transfer_offer,
    transfer_refused_to_former,
    welcome_invited,
)
from app.services.membership_lifecycle import (
    FamilyFullError,
    JoinBlockReason,
    convert_join_with_own_budget,
    evaluate_join_from_own_budget,
)
from app.services.ownership_transfer import (
    accept_ownership_transfer,
    refuse_ownership_transfer,
    request_ownership_transfer,
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
    monkeypatch.setattr(
        "app.services.ownership_transfer.resolve_bot", fake_resolve_bot
    )
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
async def test_remove_member_remaps_personal_txn_categories_by_translation_key(
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

    food_parent = ExpenseCategory(
        family_budget_id=budget.id,
        name="Еда",
        translation_key="food",
    )
    session.add(food_parent)
    await session.flush()
    groceries = ExpenseCategory(
        family_budget_id=budget.id,
        name="Продукты",
        parent_id=food_parent.id,
        translation_key="groceries",
    )
    invented = ExpenseCategory(
        family_budget_id=budget.id,
        name="Моя категория",
        parent_id=food_parent.id,
        translation_key=None,
    )
    session.add_all([groceries, invented])
    await session.flush()

    personal_wallet = Wallet(
        family_budget_id=budget.id,
        name="Member Personal",
        currency="UZS",
        is_personal=True,
        owner_user_id=member.id,
    )
    session.add(personal_wallet)
    await session.flush()

    seeded_txn = Transaction(
        family_budget_id=budget.id,
        type="expense",
        wallet_id=personal_wallet.id,
        amount=300,
        expense_category_id=groceries.id,
        created_by_user_id=member.id,
        transaction_date=datetime.now(UTC),
    )
    invented_txn = Transaction(
        family_budget_id=budget.id,
        type="expense",
        wallet_id=personal_wallet.id,
        amount=150,
        expense_category_id=invented.id,
        created_by_user_id=member.id,
        transaction_date=datetime.now(UTC),
    )
    session.add_all([seeded_txn, invented_txn])
    await session.flush()

    old_groceries_id = groceries.id
    old_invented_id = invented.id

    _mock_bot(monkeypatch)

    delete_resp = await client.delete(
        f"/api/v1/members/{member.id}",
        headers=auth_headers(owner_tid),
    )
    assert delete_resp.status_code == 200

    await session.refresh(member)
    new_budget_id = member.family_budget_id

    new_groceries = await session.scalar(
        select(ExpenseCategory).where(
            ExpenseCategory.family_budget_id == new_budget_id,
            ExpenseCategory.translation_key == "groceries",
            ExpenseCategory.is_deleted.is_(False),
        )
    )
    assert new_groceries is not None
    assert new_groceries.id != old_groceries_id

    await session.refresh(seeded_txn)
    await session.refresh(invented_txn)
    assert seeded_txn.expense_category_id == new_groceries.id
    assert invented_txn.expense_category_id is None
    assert invented_txn.expense_category_id != old_invented_id


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


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_evaluate_join_other_members_before_wallet_cap() -> None:
    async with rollback_session() as session:
        owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        solo_tid = owner_tid + 1
        target_tid = owner_tid + 2
        _, target = await create_user_with_budget(
            session, telegram_id=target_tid, invite_token=f"target-{uuid.uuid4()}"
        )
        owner, shared_budget = await create_user_with_budget(
            session, telegram_id=owner_tid, role="owner"
        )
        member, _ = await create_user_with_budget(
            session,
            telegram_id=solo_tid,
            role="member",
            family_budget_id=shared_budget.id,
        )
        for i in range(PERSONAL_WALLET_LIMIT + 2):
            session.add(
                Wallet(
                    family_budget_id=shared_budget.id,
                    name=f"Extra {i}",
                    currency="UZS",
                    is_personal=False,
                )
            )
        await session.flush()

        block = await evaluate_join_from_own_budget(session, owner, target)
        assert block == JoinBlockReason.HAS_OTHER_MEMBERS


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_evaluate_join_wallet_cap_when_solo() -> None:
    async with rollback_session() as session:
        solo_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        target_tid = solo_tid + 1
        solo, solo_budget = await create_user_with_budget(
            session, telegram_id=solo_tid, role="owner"
        )
        _, target = await create_user_with_budget(
            session, telegram_id=target_tid, invite_token=f"target-{uuid.uuid4()}"
        )
        for i in range(PERSONAL_WALLET_LIMIT + 1):
            session.add(
                Wallet(
                    family_budget_id=solo_budget.id,
                    name=f"Wallet {i}",
                    currency="UZS",
                    is_personal=False,
                )
            )
        await session.flush()

        block = await evaluate_join_from_own_budget(session, solo, target)
        assert block == JoinBlockReason.PERSONAL_WALLET_CAP


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_convert_join_moves_all_wallets_as_personal_and_closes_old_budget() -> None:
    async with rollback_session() as session:
        solo_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        target_tid = solo_tid + 1
        solo, solo_budget = await create_user_with_budget(
            session, telegram_id=solo_tid, role="owner"
        )
        _, target = await create_user_with_budget(
            session,
            telegram_id=target_tid,
            role="owner",
            invite_token=f"target-{uuid.uuid4()}",
        )
        await copy_seed_data(session, solo_budget.id)
        await session.flush()

        default_wallet = Wallet(
            family_budget_id=solo_budget.id,
            name="Default",
            currency="UZS",
            is_personal=False,
        )
        session.add(default_wallet)
        await session.flush()
        solo.default_wallet_id = default_wallet.id

        old_wallet_ids = [
            w.id
            for w in (
                await session.scalars(
                    select(Wallet).where(
                        Wallet.family_budget_id == solo_budget.id,
                        Wallet.is_deleted.is_(False),
                    )
                )
            ).all()
        ]
        assert len(old_wallet_ids) >= len(SEED_WALLETS) + 1

        session.add(
            Transaction(
                family_budget_id=solo_budget.id,
                type="income",
                wallet_id=default_wallet.id,
                amount=900,
                created_by_user_id=solo.id,
                transaction_date=datetime.now(UTC),
            )
        )
        await session.flush()
        old_budget_id = solo_budget.id

        await convert_join_with_own_budget(session, user=solo, target=target)
        await session.flush()

        await session.refresh(solo)
        await session.refresh(solo_budget)
        assert solo.role == "member"
        assert solo.family_budget_id == target.id
        assert solo.default_wallet_id == default_wallet.id
        assert solo_budget.is_deleted is True

        moved_wallets = (
            await session.scalars(
                select(Wallet).where(
                    Wallet.family_budget_id == target.id,
                    Wallet.owner_user_id == solo.id,
                    Wallet.is_deleted.is_(False),
                )
            )
        ).all()
        assert len(moved_wallets) == len(old_wallet_ids)
        assert all(w.is_personal for w in moved_wallets)

        txn = (
            await session.scalars(
                select(Transaction).where(
                    Transaction.wallet_id == default_wallet.id,
                    Transaction.is_deleted.is_(False),
                )
            )
        ).one()
        assert txn.family_budget_id == target.id


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_convert_join_deletes_active_goals() -> None:
    async with rollback_session() as session:
        solo_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        target_tid = solo_tid + 1
        solo, solo_budget = await create_user_with_budget(
            session, telegram_id=solo_tid, role="owner"
        )
        _, target = await create_user_with_budget(
            session, telegram_id=target_tid, role="owner"
        )
        wallet = Wallet(
            family_budget_id=solo_budget.id,
            name="Shared",
            currency="UZS",
            is_personal=False,
        )
        session.add(wallet)
        await session.flush()
        session.add(
            Goal(
                family_budget_id=solo_budget.id,
                wallet_id=wallet.id,
                name="Накопления",
                target_amount=1_000_000,
                currency="UZS",
                status="active",
            )
        )
        await session.flush()

        await convert_join_with_own_budget(session, user=solo, target=target)
        await session.flush()

        remaining = await session.scalar(
            select(func.count()).select_from(Goal).where(Goal.wallet_id == wallet.id)
        )
        assert remaining == 0


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_convert_join_remaps_invented_category_to_null() -> None:
    async with rollback_session() as session:
        solo_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        target_tid = solo_tid + 1
        solo, solo_budget = await create_user_with_budget(
            session, telegram_id=solo_tid, role="owner"
        )
        target_owner, target = await create_user_with_budget(
            session, telegram_id=target_tid, role="owner"
        )
        await copy_seed_data(session, target.id)
        await session.flush()

        parent = ExpenseCategory(
            family_budget_id=solo_budget.id,
            name="Еда",
            translation_key="food",
        )
        session.add(parent)
        await session.flush()
        invented = ExpenseCategory(
            family_budget_id=solo_budget.id,
            name="Моя",
            parent_id=parent.id,
            translation_key=None,
        )
        session.add(invented)
        wallet = Wallet(
            family_budget_id=solo_budget.id,
            name="W",
            currency="UZS",
            is_personal=False,
        )
        session.add(wallet)
        await session.flush()
        txn = Transaction(
            family_budget_id=solo_budget.id,
            type="expense",
            wallet_id=wallet.id,
            amount=100,
            expense_category_id=invented.id,
            created_by_user_id=solo.id,
            transaction_date=datetime.now(UTC),
        )
        session.add(txn)
        await session.flush()

        await convert_join_with_own_budget(session, user=solo, target=target)
        await session.flush()

        await session.refresh(txn)
        assert txn.expense_category_id is None


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_convert_join_raises_when_target_family_full() -> None:
    async with rollback_session() as session:
        solo_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        solo, _ = await create_user_with_budget(
            session, telegram_id=solo_tid, role="owner"
        )
        target = FamilyBudget(invite_token=f"full-{uuid.uuid4()}")
        session.add(target)
        await session.flush()
        for i in range(MEMBER_LIMIT):
            session.add(
                User(
                    telegram_id=solo_tid + i + 10,
                    family_budget_id=target.id,
                    role="owner" if i == 0 else "member",
                    language="ru",
                )
            )
        await session.flush()

        with pytest.raises(FamilyFullError):
            await convert_join_with_own_budget(session, user=solo, target=target)


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_convert_join_leaves_target_shared_aggregates_unchanged() -> None:
    async with rollback_session() as session:
        solo_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        target_tid = solo_tid + 1
        solo, solo_budget = await create_user_with_budget(
            session, telegram_id=solo_tid, role="owner"
        )
        target_owner, target = await create_user_with_budget(
            session, telegram_id=target_tid, role="owner"
        )
        shared = Wallet(
            family_budget_id=target.id,
            name="Family Shared",
            currency="UZS",
            is_personal=False,
        )
        session.add(shared)
        await session.flush()
        session.add(
            Transaction(
                family_budget_id=target.id,
                type="expense",
                wallet_id=shared.id,
                amount=400,
                created_by_user_id=target_owner.id,
                transaction_date=datetime.now(UTC),
            )
        )
        solo_wallet = Wallet(
            family_budget_id=solo_budget.id,
            name="Solo",
            currency="UZS",
            is_personal=False,
        )
        session.add(solo_wallet)
        await session.flush()

        before_income, before_expense = await _wallet_txn_totals(session, shared.id)

        await convert_join_with_own_budget(session, user=solo, target=target)
        await session.flush()

        after_income, after_expense = await _wallet_txn_totals(session, shared.id)
        assert after_income == before_income
        assert after_expense == before_expense


class TestInviteStartRefusals:
    @pytest.mark.anyio
    async def test_existing_user_invalid_invite_gets_prd_text(self) -> None:
        from types import SimpleNamespace

        from bot.onboarding import start_handler

        telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=telegram_id),
            answer=AsyncMock(),
        )
        command = SimpleNamespace(args="invite_bad-token")
        state = SimpleNamespace(set_state=AsyncMock(), update_data=AsyncMock())

        async with rollback_session() as session:
            await create_user_with_budget(session, telegram_id=telegram_id)
            user = await session.scalar(
                select(User).where(User.telegram_id == telegram_id)
            )
            assert user is not None

            class SessionContext:
                async def __aenter__(self):
                    return session

                async def __aexit__(self, *_args):
                    return None

            with patch(
                "bot.onboarding.async_session_factory",
                return_value=SessionContext(),
            ):
                await start_handler(message, command, state)

        message.answer.assert_awaited_once()
        assert invite_link_invalid() in message.answer.await_args.args[0]

    @pytest.mark.anyio
    async def test_solo_owner_with_too_many_wallets_gets_cap_not_confirm(self) -> None:
        from types import SimpleNamespace

        from bot.onboarding import start_handler

        owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        target_token = f"invite-{uuid.uuid4()}"
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=owner_tid),
            answer=AsyncMock(),
        )
        command = SimpleNamespace(args=f"invite_{target_token}")
        state = SimpleNamespace(set_state=AsyncMock(), update_data=AsyncMock())

        async with rollback_session() as session:
            owner, budget = await create_user_with_budget(
                session, telegram_id=owner_tid, role="owner"
            )
            target = FamilyBudget(invite_token=target_token, name="Target Family")
            session.add(target)
            await session.flush()
            for i in range(PERSONAL_WALLET_LIMIT + 1):
                session.add(
                    Wallet(
                        family_budget_id=budget.id,
                        name=f"W{i}",
                        currency="UZS",
                        is_personal=False,
                    )
                )
            await session.flush()

            class SessionContext:
                async def __aenter__(self):
                    return session

                async def __aexit__(self, *_args):
                    return None

            with patch(
                "bot.onboarding.async_session_factory",
                return_value=SessionContext(),
            ):
                await start_handler(message, command, state)

        text = message.answer.await_args.args[0]
        assert join_confirm_prompt("Target Family") not in text
        assert str(PERSONAL_WALLET_LIMIT + 1) in text
        assert "личных можно иметь не больше 5" in text

    @pytest.mark.anyio
    async def test_solo_owner_eligible_gets_confirm_prompt(self) -> None:
        from types import SimpleNamespace

        from bot.onboarding import start_handler

        owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        target_token = f"invite-{uuid.uuid4()}"
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=owner_tid),
            answer=AsyncMock(),
        )
        command = SimpleNamespace(args=f"invite_{target_token}")
        state = SimpleNamespace(set_state=AsyncMock(), update_data=AsyncMock())

        async with rollback_session() as session:
            await create_user_with_budget(session, telegram_id=owner_tid, role="owner")
            target = FamilyBudget(
                invite_token=target_token, name="Семья Юсуповых"
            )
            session.add(target)
            await session.flush()

            class SessionContext:
                async def __aenter__(self):
                    return session

                async def __aexit__(self, *_args):
                    return None

            with patch(
                "bot.onboarding.async_session_factory",
                return_value=SessionContext(),
            ):
                await start_handler(message, command, state)

        text = message.answer.await_args.args[0]
        assert text == join_confirm_prompt("Семья Юсуповых")
        assert message.answer.await_args.kwargs["reply_markup"] is not None


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_transfer_accept_swaps_roles_and_notifies_former_and_remaining(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = _mock_bot(monkeypatch)

    async with rollback_session() as session:
        owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        recipient_tid = owner_tid + 1
        other_tid = owner_tid + 2
        owner, budget = await create_user_with_budget(
            session,
            telegram_id=owner_tid,
            role="owner",
            first_name="Alice",
        )
        budget.name = "Семья Каримовых"
        recipient, _ = await create_user_with_budget(
            session,
            telegram_id=recipient_tid,
            role="member",
            first_name="Рустам",
            family_budget_id=budget.id,
        )
        other, _ = await create_user_with_budget(
            session,
            telegram_id=other_tid,
            role="member",
            first_name="Bob",
            family_budget_id=budget.id,
        )
        await session.flush()

        transfer = await request_ownership_transfer(
            session,
            owner=owner,
            recipient=recipient,
            budget=budget,
            bot=None,
        )
        assert transfer.status == "pending"
        assert bot.send_message.await_count == 1
        assert transfer_offer("Семья Каримовых") in bot.send_message.await_args.args[1]

        bot.send_message.reset_mock()

        await accept_ownership_transfer(
            session,
            transfer_id=transfer.id,
            actor=recipient,
            bot=None,
        )
        await session.flush()

        await session.refresh(owner)
        await session.refresh(recipient)
        await session.refresh(other)
        await session.refresh(transfer)

        assert owner.role == "member"
        assert recipient.role == "owner"
        assert transfer.status == "accepted"

        messages = {
            call.args[0]: call.args[1]
            for call in bot.send_message.await_args_list
        }
        assert messages[owner.telegram_id] == transfer_accepted_to_former(
            "Рустам", "Семья Каримовых"
        )
        assert messages[other.telegram_id] == transfer_accepted_to_others(
            "Рустам", "Семья Каримовых"
        )
        assert recipient.telegram_id not in messages


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_transfer_refuse_keeps_owner_and_notifies_former(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = _mock_bot(monkeypatch)

    async with rollback_session() as session:
        owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
        recipient_tid = owner_tid + 1
        owner, budget = await create_user_with_budget(
            session,
            telegram_id=owner_tid,
            role="owner",
            first_name="Alice",
        )
        recipient, _ = await create_user_with_budget(
            session,
            telegram_id=recipient_tid,
            role="member",
            first_name="Рустам",
            family_budget_id=budget.id,
        )
        await session.flush()

        transfer = await request_ownership_transfer(
            session,
            owner=owner,
            recipient=recipient,
            budget=budget,
            bot=None,
        )
        bot.send_message.reset_mock()

        await refuse_ownership_transfer(
            session,
            transfer_id=transfer.id,
            actor=recipient,
            bot=None,
        )
        await session.flush()

        await session.refresh(owner)
        await session.refresh(recipient)
        await session.refresh(transfer)

        assert owner.role == "owner"
        assert recipient.role == "member"
        assert transfer.status == "refused"

        bot.send_message.assert_awaited_once_with(
            owner.telegram_id,
            transfer_refused_to_former("Рустам"),
        )


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_post_transfer_creates_pending_and_cancels_previous(
    api_client: tuple[AsyncClient, AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = api_client
    bot = _mock_bot(monkeypatch)
    owner_tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    member_a_tid = owner_tid + 1
    member_b_tid = owner_tid + 2
    owner, budget = await create_user_with_budget(
        session,
        telegram_id=owner_tid,
        role="owner",
    )
    budget.name = "Семья Каримовых"
    member_a, _ = await create_user_with_budget(
        session,
        telegram_id=member_a_tid,
        role="member",
        first_name="A",
        family_budget_id=budget.id,
    )
    member_b, _ = await create_user_with_budget(
        session,
        telegram_id=member_b_tid,
        role="member",
        first_name="B",
        family_budget_id=budget.id,
    )
    await session.flush()

    first = await client.post(
        f"/api/v1/members/{member_a.id}/transfer",
        headers=auth_headers(owner_tid),
    )
    assert first.status_code == 200
    first_id = uuid.UUID(first.json()["id"])

    second = await client.post(
        f"/api/v1/members/{member_b.id}/transfer",
        headers=auth_headers(owner_tid),
    )
    assert second.status_code == 200

    first_row = await session.get(OwnershipTransfer, first_id)
    assert first_row is not None
    assert first_row.status == "cancelled"

    pending = (
        await session.scalars(
            select(OwnershipTransfer).where(
                OwnershipTransfer.family_budget_id == budget.id,
                OwnershipTransfer.status == "pending",
            )
        )
    ).all()
    assert len(pending) == 1
    assert pending[0].to_user_id == member_b.id
    assert bot.send_message.await_count == 2
