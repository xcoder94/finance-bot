import socket
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.income_category import IncomeCategory
from app.models.quick_entry_pending import QuickEntryPending
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from bot.quick_entry.handlers import (
    handle_quick_entry_delete,
    handle_quick_entry_type,
    handle_quick_entry_wallet_list,
    handle_quick_entry_wallet_set,
)
from bot.quick_entry.pending import create_pending
from bot.quick_entry.texts import MSG_GONE, MSG_TYPE_QUESTION

TASHKENT = ZoneInfo("Asia/Tashkent")


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


async def create_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    role: str = "owner",
    budget: FamilyBudget | None = None,
) -> tuple[User, FamilyBudget]:
    if budget is None:
        budget = FamilyBudget(invite_token=f"test-{uuid.uuid4()}")
        session.add(budget)
        await session.flush()
    user = User(
        telegram_id=telegram_id,
        family_budget_id=budget.id,
        role=role,
        language="ru",
    )
    session.add(user)
    await session.flush()
    return user, budget


def make_wallet(
    budget: FamilyBudget,
    *,
    name: str,
    currency: str = "UZS",
    is_personal: bool = False,
    owner_user_id: uuid.UUID | None = None,
) -> Wallet:
    return Wallet(
        family_budget_id=budget.id,
        name=name,
        currency=currency,
        is_personal=is_personal,
        owner_user_id=owner_user_id,
    )


class SessionFactory:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def __call__(self) -> SessionFactory:
        return self

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *_args: object) -> None:
        return None


def make_callback(
    *,
    telegram_id: int,
    data: str,
    message_text: str = "card",
) -> SimpleNamespace:
    message = SimpleNamespace(
        text=message_text,
        edit_text=AsyncMock(),
        edit_reply_markup=AsyncMock(),
    )
    return SimpleNamespace(
        from_user=SimpleNamespace(id=telegram_id),
        message=message,
        data=data,
        answer=AsyncMock(),
    )


async def seed_expense_txn(
    session: AsyncSession,
    user: User,
    budget: FamilyBudget,
    *,
    amount: int = 25_000,
    wallet_name: str = "Наличный сум",
) -> tuple[Transaction, Wallet, ExpenseCategory]:
    wallet = make_wallet(budget, name=wallet_name)
    transport = ExpenseCategory(family_budget_id=budget.id, name="Транспорт")
    session.add_all([wallet, transport])
    await session.flush()
    taxi = ExpenseCategory(
        family_budget_id=budget.id, name="Такси", parent_id=transport.id
    )
    session.add(taxi)
    await session.flush()
    txn = Transaction(
        family_budget_id=budget.id,
        type="expense",
        wallet_id=wallet.id,
        amount=amount,
        expense_category_id=taxi.id,
        comment="такси до работы",
        created_by_user_id=user.id,
        transaction_date=datetime(2026, 8, 1, 12, 0, tzinfo=TASHKENT),
    )
    session.add(txn)
    await session.flush()
    return txn, wallet, taxi


pytestmark = [
    pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available"),
    pytest.mark.anyio,
]


class TestDeleteCallback:
    async def test_soft_deletes_and_removes_buttons(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_100_001)
            txn, _, _ = await seed_expense_txn(session, user, budget)
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            callback = make_callback(
                telegram_id=user.telegram_id,
                data=f"qe:del:{txn.id}",
            )
            await handle_quick_entry_delete(callback, SimpleNamespace())

            await session.refresh(txn)
            assert txn.is_deleted is True
            callback.message.edit_reply_markup.assert_awaited_once_with(
                reply_markup=None
            )
            callback.answer.assert_awaited_once()

    async def test_gone_when_missing_or_soft_deleted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_100_002)
            txn, _, _ = await seed_expense_txn(session, user, budget)
            txn.is_deleted = True
            await session.flush()
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            callback = make_callback(
                telegram_id=user.telegram_id,
                data=f"qe:del:{txn.id}",
            )
            await handle_quick_entry_delete(callback, SimpleNamespace())

            callback.answer.assert_awaited_once_with(MSG_GONE)
            callback.message.edit_reply_markup.assert_not_awaited()


class TestWalletListCallback:
    async def test_shows_writer_visible_wallets(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            member_a, budget = await create_user(session, telegram_id=9_101_001)
            member_b, _ = await create_user(
                session, telegram_id=9_101_002, role="member", budget=budget
            )
            shared = make_wallet(budget, name="Shared wallet")
            personal_a = make_wallet(
                budget,
                name="A-personal",
                is_personal=True,
                owner_user_id=member_a.id,
            )
            session.add_all([shared, personal_a])
            await session.flush()
            txn = Transaction(
                family_budget_id=budget.id,
                type="expense",
                wallet_id=shared.id,
                amount=1_000,
                created_by_user_id=member_b.id,
                transaction_date=datetime(2026, 8, 1, 12, 0, tzinfo=TASHKENT),
            )
            session.add(txn)
            await session.flush()

            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )
            callback = make_callback(
                telegram_id=member_b.telegram_id,
                data=f"qe:wal:{txn.id}",
            )
            await handle_quick_entry_wallet_list(callback, SimpleNamespace())

            callback.message.edit_reply_markup.assert_awaited_once()
            kb = callback.message.edit_reply_markup.await_args.kwargs["reply_markup"]
            wallet_names = [row[0].text for row in kb.inline_keyboard]
            assert wallet_names == ["Shared wallet"]
            assert "A-personal" not in wallet_names

    async def test_gone_when_transaction_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_101_003)
            missing_id = uuid.uuid4()
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )
            callback = make_callback(
                telegram_id=user.telegram_id,
                data=f"qe:wal:{missing_id}",
            )
            await handle_quick_entry_wallet_list(callback, SimpleNamespace())
            callback.answer.assert_awaited_once_with(MSG_GONE)


class TestWalletSetCallback:
    async def test_updates_wallet_and_rerenders_card(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_102_001)
            txn, wallet_a, taxi = await seed_expense_txn(session, user, budget)
            wallet_b = make_wallet(budget, name="Карта сум")
            session.add(wallet_b)
            session.add(
                Transaction(
                    family_budget_id=budget.id,
                    type="income",
                    wallet_id=wallet_a.id,
                    amount=1_300_000,
                    created_by_user_id=user.id,
                    transaction_date=datetime(2026, 8, 1, 12, 0, tzinfo=TASHKENT),
                )
            )
            await session.flush()

            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )
            callback = make_callback(
                telegram_id=user.telegram_id,
                data=f"qe:walset:{txn.id}:{wallet_b.id}",
            )
            await handle_quick_entry_wallet_set(callback, SimpleNamespace())

            await session.refresh(txn)
            assert txn.wallet_id == wallet_b.id
            callback.message.edit_text.assert_awaited_once()
            card_text = callback.message.edit_text.await_args.args[0]
            assert "Карта сум" in card_text
            assert "Такси" in card_text
            assert callback.message.edit_text.await_args.kwargs["parse_mode"] == "Markdown"
            kb = callback.message.edit_text.await_args.kwargs["reply_markup"]
            assert kb.inline_keyboard[0][0].text == "Кошелёк"

    async def test_gone_when_transaction_soft_deleted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_102_002)
            txn, wallet, _ = await seed_expense_txn(session, user, budget)
            txn.is_deleted = True
            await session.flush()
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )
            callback = make_callback(
                telegram_id=user.telegram_id,
                data=f"qe:walset:{txn.id}:{wallet.id}",
            )
            await handle_quick_entry_wallet_set(callback, SimpleNamespace())
            callback.answer.assert_awaited_once_with(MSG_GONE)


class TestTypeCallback:
    async def test_expense_creates_record_spends_quota_replaces_question(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_103_001)
            wallet = make_wallet(budget, name="Карта сум")
            events = ExpenseCategory(family_budget_id=budget.id, name="События и тои")
            session.add_all([wallet, events])
            await session.flush()
            gifts = ExpenseCategory(
                family_budget_id=budget.id, name="Подарки", parent_id=events.id
            )
            session.add(gifts)
            await session.flush()

            pending = await create_pending(
                session,
                user_id=user.id,
                family_budget_id=budget.id,
                amount=500_000,
                currency="UZS",
                wallet_id=wallet.id,
                category_raw="Подарки",
                comment=None,
                operation_date=date(2026, 8, 1),
            )

            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )
            callback = make_callback(
                telegram_id=user.telegram_id,
                data=f"qe:type:{pending.id}:expense",
                message_text=f"**500 000 сум** · Подарки\n{MSG_TYPE_QUESTION}",
            )
            await handle_quick_entry_type(callback, SimpleNamespace())

            txns = (
                await session.scalars(
                    select(Transaction).where(Transaction.family_budget_id == budget.id)
                )
            ).all()
            assert len(txns) == 1
            assert txns[0].type == "expense"
            assert txns[0].expense_category_id == gifts.id
            assert txns[0].transaction_date == datetime(
                2026, 8, 1, 12, 0, tzinfo=TASHKENT
            )

            pending_row = await session.get(QuickEntryPending, pending.id)
            assert pending_row is None

            await session.refresh(budget)
            assert budget.daily_model_calls == 1

            callback.message.edit_text.assert_awaited_once()
            card_text = callback.message.edit_text.await_args.args[0]
            assert "➖" in card_text and "500 000 сум" in card_text and "Подарки" in card_text

    async def test_income_podarki_via_button_choice(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_103_002)
            wallet = make_wallet(budget, name="Карта сум")
            income_gifts = IncomeCategory(family_budget_id=budget.id, name="Подарки")
            session.add_all([wallet, income_gifts])
            await session.flush()

            pending = await create_pending(
                session,
                user_id=user.id,
                family_budget_id=budget.id,
                amount=500_000,
                currency="UZS",
                wallet_id=wallet.id,
                category_raw="Подарки",
                comment=None,
                operation_date=date(2026, 8, 1),
            )

            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )
            callback = make_callback(
                telegram_id=user.telegram_id,
                data=f"qe:type:{pending.id}:income",
            )
            await handle_quick_entry_type(callback, SimpleNamespace())

            txn = await session.scalar(
                select(Transaction).where(Transaction.family_budget_id == budget.id)
            )
            assert txn is not None
            assert txn.type == "income"
            assert txn.income_category_id == income_gifts.id

    async def test_no_category_uses_bez_kategorii(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_103_003)
            wallet = make_wallet(budget, name="Карта сум")
            session.add(wallet)
            await session.flush()

            pending = await create_pending(
                session,
                user_id=user.id,
                family_budget_id=budget.id,
                amount=300_000,
                currency="UZS",
                wallet_id=wallet.id,
                category_raw=None,
                comment="Азиз",
                operation_date=date(2026, 8, 1),
            )

            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )
            callback = make_callback(
                telegram_id=user.telegram_id,
                data=f"qe:type:{pending.id}:expense",
            )
            await handle_quick_entry_type(callback, SimpleNamespace())

            txn = await session.scalar(
                select(Transaction).where(Transaction.family_budget_id == budget.id)
            )
            assert txn is not None
            assert txn.expense_category_id is None
            card_text = callback.message.edit_text.await_args.args[0]
            assert "Без категории" in card_text
            assert "Азиз" in card_text

    async def test_double_tap_returns_gone(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_103_004)
            wallet = make_wallet(budget, name="Карта сум")
            session.add(wallet)
            await session.flush()

            pending = await create_pending(
                session,
                user_id=user.id,
                family_budget_id=budget.id,
                amount=10_000,
                currency="UZS",
                wallet_id=wallet.id,
                category_raw=None,
                comment=None,
                operation_date=date(2026, 8, 1),
            )

            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )
            callback1 = make_callback(
                telegram_id=user.telegram_id,
                data=f"qe:type:{pending.id}:expense",
            )
            callback2 = make_callback(
                telegram_id=user.telegram_id,
                data=f"qe:type:{pending.id}:expense",
            )
            await handle_quick_entry_type(callback1, SimpleNamespace())
            await handle_quick_entry_type(callback2, SimpleNamespace())

            txns = (
                await session.scalars(
                    select(Transaction).where(Transaction.family_budget_id == budget.id)
                )
            ).all()
            assert len(txns) == 1
            callback2.answer.assert_awaited_once_with(MSG_GONE)
