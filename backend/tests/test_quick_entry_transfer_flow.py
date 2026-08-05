import socket
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.parsing.stub import StubParser
from app.parsing.types import ParseResponse, ParsedOperation
from app.services.quick_entry_balance import wallet_balance
from bot.quick_entry.handlers import (
    handle_quick_entry_delete,
    handle_quick_entry_text,
    set_parser_override,
)
from bot.quick_entry.texts import MSG_EXCHANGE_RATE_REQUIRED


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
    budget: FamilyBudget | None = None,
) -> tuple[User, FamilyBudget]:
    if budget is None:
        budget = FamilyBudget(invite_token=f"test-{uuid.uuid4()}")
        session.add(budget)
        await session.flush()
    user = User(
        telegram_id=telegram_id,
        family_budget_id=budget.id,
        role="owner",
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
) -> Wallet:
    return Wallet(family_budget_id=budget.id, name=name, currency=currency)


def make_message(*, telegram_id: int, text: str) -> SimpleNamespace:
    return SimpleNamespace(
        from_user=SimpleNamespace(id=telegram_id),
        text=text,
        answer=AsyncMock(),
    )


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
        delete=AsyncMock(),
    )
    return SimpleNamespace(
        from_user=SimpleNamespace(id=telegram_id),
        message=message,
        data=data,
        answer=AsyncMock(),
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


async def seed_transfer_wallets(
    session: AsyncSession, budget: FamilyBudget, user: User
) -> tuple[Wallet, Wallet, Wallet, Wallet]:
    cash_uzs = make_wallet(budget, name="Наличный сум", currency="UZS")
    card_uzs = make_wallet(budget, name="Карта сум", currency="UZS")
    cash_usd = make_wallet(budget, name="Наличный USD", currency="USD")
    card_usd = make_wallet(budget, name="Карта USD", currency="USD")
    session.add_all([cash_uzs, card_uzs, cash_usd, card_usd])
    user.default_wallet_id = card_uzs.id
    await session.flush()
    return cash_uzs, card_uzs, cash_usd, card_usd


async def seed_income(
    session: AsyncSession,
    user: User,
    budget: FamilyBudget,
    wallet: Wallet,
    amount: int,
) -> None:
    session.add(
        Transaction(
            family_budget_id=budget.id,
            type="income",
            wallet_id=wallet.id,
            amount=amount,
            created_by_user_id=user.id,
            transaction_date=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
        )
    )
    await session.flush()


async def seed_taxi_setup(
    session: AsyncSession, user: User, budget: FamilyBudget
) -> tuple[Wallet, ExpenseCategory]:
    wallet = make_wallet(budget, name="Наличный сум")
    transport = ExpenseCategory(family_budget_id=budget.id, name="Транспорт")
    session.add_all([wallet, transport])
    await session.flush()
    taxi = ExpenseCategory(
        family_budget_id=budget.id, name="Такси", parent_id=transport.id
    )
    session.add(taxi)
    user.default_wallet_id = wallet.id
    await session.flush()
    return wallet, taxi


def _keyboard_button_texts(reply_markup: object) -> list[str]:
    return [btn.text for row in reply_markup.inline_keyboard for btn in row]  # type: ignore[attr-defined]


pytestmark = [
    pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available"),
    pytest.mark.anyio,
]


@pytest.fixture(autouse=True)
def reset_parser_override() -> AsyncIterator[None]:
    set_parser_override(None)
    yield
    set_parser_override(None)


class TestSameCurrencyTransferFlow:
    async def test_transfer_card_and_balances(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_010_001)
            cash_uzs, card_uzs, _, _ = await seed_transfer_wallets(
                session, budget, user
            )
            await seed_income(session, user, budget, card_uzs, 1_000_000)

            text = "переложил 500 тысяч с карты на наличные"
            set_parser_override(StubParser())
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )
            monkeypatch.setattr(
                "bot.quick_entry.handlers.resolve_operation_date",
                lambda _text, now=None: date(2026, 8, 1),
            )

            message = make_message(telegram_id=user.telegram_id, text=text)
            await handle_quick_entry_text(message, SimpleNamespace())

            message.answer.assert_awaited_once()
            card_text = message.answer.await_args.args[0]
            assert card_text == (
                "↔️ **500 000 сум** · Перевод\n"
                "Карта сум → Наличный сум · 1 августа\n"
                "Карта сум: 500 000 · Наличный сум: 500 000"
            )
            kb = message.answer.await_args.kwargs["reply_markup"]
            assert "Кошелёк" not in _keyboard_button_texts(kb)
            assert _keyboard_button_texts(kb) == ["Изменить", "Удалить"]

            txns = (
                await session.scalars(
                    select(Transaction).where(Transaction.family_budget_id == budget.id)
                )
            ).all()
            assert len(txns) == 2
            transfer = next(t for t in txns if t.type == "transfer")
            assert transfer.amount == 500_000
            assert await wallet_balance(session, card_uzs.id) == 500_000
            assert await wallet_balance(session, cash_uzs.id) == 500_000


class TestExchangeWithRateFlow:
    async def test_exchange_card_and_balances(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_010_002)
            card_uzs = make_wallet(budget, name="Карта сум", currency="UZS")
            card_usd = make_wallet(budget, name="Карта USD", currency="USD")
            session.add_all([card_uzs, card_usd])
            user.default_wallet_id = card_uzs.id
            await session.flush()
            await seed_income(session, user, budget, card_usd, 500)

            text = "поменял 100 долларов на сумы по 12800"
            set_parser_override(StubParser())
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )
            monkeypatch.setattr(
                "bot.quick_entry.handlers.resolve_operation_date",
                lambda _text, now=None: date(2026, 8, 1),
            )

            message = make_message(telegram_id=user.telegram_id, text=text)
            await handle_quick_entry_text(message, SimpleNamespace())

            message.answer.assert_awaited_once()
            card_text = message.answer.await_args.args[0]
            assert card_text == (
                "🔄 **100 $ → 1 280 000 сум** · Обмен\n"
                "Курс 12 800 · 1 августа\n"
                "Карта USD: 400 $ · Карта сум: 1 280 000 сум"
            )

            txns = (
                await session.scalars(
                    select(Transaction).where(
                        Transaction.family_budget_id == budget.id,
                        Transaction.type == "transfer",
                    )
                )
            ).all()
            assert len(txns) == 1
            assert txns[0].rate == 12_800
            assert await wallet_balance(session, card_usd.id) == 400
            assert await wallet_balance(session, card_uzs.id) == 1_280_000


class TestCrossCurrencyRefusal:
    async def test_russian_no_rate_refuses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_010_003)
            _, card_uzs, _, card_usd = await seed_transfer_wallets(
                session, budget, user
            )
            await seed_income(session, user, budget, card_usd, 500)
            await seed_income(session, user, budget, card_uzs, 1_000_000)
            usd_before = await wallet_balance(session, card_usd.id)
            uzs_before = await wallet_balance(session, card_uzs.id)

            text = "перевел с карты доллара на карту сум 50$"
            set_parser_override(StubParser())
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            message = make_message(telegram_id=user.telegram_id, text=text)
            await handle_quick_entry_text(message, SimpleNamespace())

            message.answer.assert_awaited_once_with(MSG_EXCHANGE_RATE_REQUIRED)
            txns = (
                await session.scalars(
                    select(Transaction).where(
                        Transaction.family_budget_id == budget.id,
                        Transaction.type == "transfer",
                    )
                )
            ).all()
            assert txns == []
            assert await wallet_balance(session, card_usd.id) == usd_before
            assert await wallet_balance(session, card_uzs.id) == uzs_before
            await session.refresh(budget)
            assert budget.daily_unparsed == 1

    async def test_uzbek_no_rate_refuses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_010_004)
            _, card_uzs, _, card_usd = await seed_transfer_wallets(
                session, budget, user
            )
            await seed_income(session, user, budget, card_usd, 500)
            usd_before = await wallet_balance(session, card_usd.id)

            text = "dollar kartasidan so'm kartasiga 50$ o'tkazdim"
            set_parser_override(StubParser())
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            message = make_message(telegram_id=user.telegram_id, text=text)
            await handle_quick_entry_text(message, SimpleNamespace())

            message.answer.assert_awaited_once_with(MSG_EXCHANGE_RATE_REQUIRED)
            txns = (
                await session.scalars(
                    select(Transaction).where(
                        Transaction.family_budget_id == budget.id,
                        Transaction.type == "transfer",
                    )
                )
            ).all()
            assert txns == []
            assert await wallet_balance(session, card_usd.id) == usd_before
            await session.refresh(budget)
            assert budget.daily_unparsed == 1

    async def test_missing_rate_marker_refuses_even_with_stub_rate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_010_005)
            _, card_uzs, _, card_usd = await seed_transfer_wallets(
                session, budget, user
            )
            await seed_income(session, user, budget, card_usd, 500)
            usd_before = await wallet_balance(session, card_usd.id)

            text = "поменял 100 долларов на сумы 12800"
            set_parser_override(
                StubParser(
                    responses={
                        text: ParseResponse(
                            operations=[
                                ParsedOperation(
                                    type="exchange",
                                    amount=100,
                                    currency="USD",
                                    wallet_hint=None,
                                    category=None,
                                    comment=None,
                                    from_wallet_hint="Карта USD",
                                    to_wallet_hint="Карта сум",
                                    rate=12_800,
                                )
                            ]
                        )
                    }
                )
            )
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            message = make_message(telegram_id=user.telegram_id, text=text)
            await handle_quick_entry_text(message, SimpleNamespace())

            message.answer.assert_awaited_once_with(MSG_EXCHANGE_RATE_REQUIRED)
            txns = (
                await session.scalars(
                    select(Transaction).where(
                        Transaction.family_budget_id == budget.id,
                        Transaction.type == "transfer",
                    )
                )
            ).all()
            assert txns == []
            assert await wallet_balance(session, card_usd.id) == usd_before
            await session.refresh(budget)
            assert budget.daily_unparsed == 1


class TestExpenseRegression:
    async def test_taxi_expense_still_works(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_010_006)
            wallet, _ = await seed_taxi_setup(session, user, budget)
            session.add(
                Transaction(
                    family_budget_id=budget.id,
                    type="income",
                    wallet_id=wallet.id,
                    amount=1_300_000,
                    created_by_user_id=user.id,
                    transaction_date=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
                )
            )
            await session.flush()

            set_parser_override(StubParser())
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )
            monkeypatch.setattr(
                "bot.quick_entry.handlers.resolve_operation_date",
                lambda _text, now=None: date(2026, 8, 1),
            )

            message = make_message(
                telegram_id=user.telegram_id, text="такси 25 тысяч"
            )
            await handle_quick_entry_text(message, SimpleNamespace())

            message.answer.assert_awaited_once()
            card_text = message.answer.await_args.args[0]
            assert "➖ **25 000 сум** · Такси" in card_text
            txns = (
                await session.scalars(
                    select(Transaction).where(
                        Transaction.family_budget_id == budget.id,
                        Transaction.type == "expense",
                    )
                )
            ).all()
            assert len(txns) == 1


class TestTransferDelete:
    async def test_soft_delete_restores_balances(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_010_007)
            cash_uzs, card_uzs, _, _ = await seed_transfer_wallets(
                session, budget, user
            )
            await seed_income(session, user, budget, card_uzs, 1_000_000)

            card_before = await wallet_balance(session, card_uzs.id)
            cash_before = await wallet_balance(session, cash_uzs.id)

            text = "переложил 500 тысяч с карты на наличные"
            set_parser_override(StubParser())
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )
            monkeypatch.setattr(
                "bot.quick_entry.handlers.resolve_operation_date",
                lambda _text, now=None: date(2026, 8, 1),
            )

            message = make_message(telegram_id=user.telegram_id, text=text)
            await handle_quick_entry_text(message, SimpleNamespace())

            transfer = (
                await session.scalars(
                    select(Transaction).where(
                        Transaction.family_budget_id == budget.id,
                        Transaction.type == "transfer",
                    )
                )
            ).one()
            assert await wallet_balance(session, card_uzs.id) == 500_000
            assert await wallet_balance(session, cash_uzs.id) == 500_000

            callback = make_callback(
                telegram_id=user.telegram_id,
                data=f"qe:del:{transfer.id}",
            )
            await handle_quick_entry_delete(callback, SimpleNamespace())

            await session.refresh(transfer)
            assert transfer.is_deleted is True
            assert await wallet_balance(session, card_uzs.id) == card_before
            assert await wallet_balance(session, cash_uzs.id) == cash_before
            callback.answer.assert_awaited_once()
            callback.message.delete.assert_awaited_once()


class TestMixedRefusedTransferAndExpense:
    async def test_expense_created_transfer_refused_balances(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_010_008)
            cash_uzs, card_uzs, _, card_usd = await seed_transfer_wallets(
                session, budget, user
            )
            transport = ExpenseCategory(family_budget_id=budget.id, name="Транспорт")
            session.add(transport)
            await session.flush()
            taxi = ExpenseCategory(
                family_budget_id=budget.id, name="Такси", parent_id=transport.id
            )
            session.add(taxi)
            await session.flush()
            await seed_income(session, user, budget, card_usd, 500)
            await seed_income(session, user, budget, card_uzs, 1_000_000)
            await seed_income(session, user, budget, cash_uzs, 1_300_000)

            usd_before = await wallet_balance(session, card_usd.id)
            uzs_card_before = await wallet_balance(session, card_uzs.id)
            cash_before = await wallet_balance(session, cash_uzs.id)

            text = "такси 25 тысяч и перевел с карты доллара на карту сум 50$"
            set_parser_override(
                StubParser(
                    responses={
                        text: ParseResponse(
                            operations=[
                                ParsedOperation(
                                    type="expense",
                                    amount=25_000,
                                    currency="UZS",
                                    wallet_hint=None,
                                    category="Такси",
                                    comment=None,
                                ),
                                ParsedOperation(
                                    type="exchange",
                                    amount=50,
                                    currency="USD",
                                    wallet_hint=None,
                                    category=None,
                                    comment=None,
                                    from_wallet_hint="карта доллара",
                                    to_wallet_hint="карта сум",
                                    rate=None,
                                ),
                            ]
                        )
                    }
                )
            )
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )
            monkeypatch.setattr(
                "bot.quick_entry.handlers.resolve_operation_date",
                lambda _text, now=None: date(2026, 8, 1),
            )

            message = make_message(telegram_id=user.telegram_id, text=text)
            await handle_quick_entry_text(message, SimpleNamespace())

            assert message.answer.await_count == 2
            assert message.answer.await_args_list[0].args[0] == MSG_EXCHANGE_RATE_REQUIRED
            assert "➖ **25 000 сум** · Такси" in message.answer.await_args_list[1].args[0]

            transfer_txns = (
                await session.scalars(
                    select(Transaction).where(
                        Transaction.family_budget_id == budget.id,
                        Transaction.type == "transfer",
                    )
                )
            ).all()
            assert transfer_txns == []

            expense_txns = (
                await session.scalars(
                    select(Transaction).where(
                        Transaction.family_budget_id == budget.id,
                        Transaction.type == "expense",
                    )
                )
            ).all()
            assert len(expense_txns) == 1
            assert expense_txns[0].amount == 25_000

            assert await wallet_balance(session, card_usd.id) == usd_before
            assert await wallet_balance(session, card_uzs.id) == uzs_card_before
            assert await wallet_balance(session, cash_uzs.id) == cash_before - 25_000
