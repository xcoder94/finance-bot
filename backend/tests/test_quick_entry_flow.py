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
from app.models.income_category import IncomeCategory
from app.models.quick_entry_pending import QuickEntryPending
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.parsing.stub import StubParser
from app.parsing.types import (
    ParseResponse,
    ParsedOperation,
    ParserMalformed,
    ParserUnavailable,
)
from bot.quick_entry.handlers import (
    handle_quick_entry_text,
    handle_quick_entry_type,
    set_parser_override,
)
from bot.quick_entry.texts import (
    MSG_MODEL_FAIL,
    MSG_NO_AMOUNT,
    MSG_TOO_LONG,
    MSG_TOO_MANY_OPS,
    MSG_TYPE_QUESTION,
    currency_missing_text,
)


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


pytestmark = [
    pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available"),
    pytest.mark.anyio,
]


@pytest.fixture(autouse=True)
def reset_parser_override() -> AsyncIterator[None]:
    set_parser_override(None)
    yield
    set_parser_override(None)


class TestSingleExpenseCard:
    async def test_single_expense_card_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_001_001)
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

            set_parser_override(
                StubParser(
                    responses={
                        "такси 25 тысяч": ParseResponse(
                            operations=[
                                ParsedOperation(
                                    type="expense",
                                    amount=25_000,
                                    currency="UZS",
                                    wallet_hint=None,
                                    category="Такси",
                                    comment="такси до работы",
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
            monkeypatch.setattr(
                "bot.quick_entry.handlers.resolve_operation_date",
                lambda _text, now=None: date(2026, 8, 1),
            )

            message = make_message(telegram_id=user.telegram_id, text="такси 25 тысяч")
            await handle_quick_entry_text(message, SimpleNamespace())

            message.answer.assert_awaited_once()
            card_text = message.answer.await_args.args[0]
            assert card_text == (
                "➖ **25 000 сум** · Такси\n"
                "Наличный сум · 1 августа\n"
                "Осталось: 1 275 000 сум"
            )
            assert message.answer.await_args.kwargs.get("parse_mode") == "Markdown"
            assert message.answer.await_args.kwargs["reply_markup"] is not None


class TestThreeOperations:
    async def test_three_ops_send_three_cards(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_002_001)
            wallet = make_wallet(budget, name="Карта сум")
            food = ExpenseCategory(family_budget_id=budget.id, name="Еда")
            session.add_all([wallet, food])
            await session.flush()
            groceries = ExpenseCategory(
                family_budget_id=budget.id, name="Продукты", parent_id=food.id
            )
            transport = ExpenseCategory(family_budget_id=budget.id, name="Транспорт")
            session.add_all([groceries, transport])
            await session.flush()
            taxi = ExpenseCategory(
                family_budget_id=budget.id, name="Такси", parent_id=transport.id
            )
            session.add(taxi)
            user.default_wallet_id = wallet.id
            await session.flush()

            text = "три операции"
            set_parser_override(
                StubParser(
                    responses={
                        text: ParseResponse(
                            operations=[
                                ParsedOperation(
                                    type="expense",
                                    amount=10_000,
                                    currency="UZS",
                                    wallet_hint=None,
                                    category="Продукты",
                                    comment=None,
                                ),
                                ParsedOperation(
                                    type="expense",
                                    amount=5_000,
                                    currency="UZS",
                                    wallet_hint=None,
                                    category="Такси",
                                    comment=None,
                                ),
                                ParsedOperation(
                                    type="income",
                                    amount=50_000,
                                    currency="UZS",
                                    wallet_hint=None,
                                    category="Зарплата",
                                    comment=None,
                                ),
                            ]
                        )
                    }
                )
            )
            salary = IncomeCategory(family_budget_id=budget.id, name="Зарплата")
            session.add(salary)
            await session.flush()

            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            message = make_message(telegram_id=user.telegram_id, text=text)
            await handle_quick_entry_text(message, SimpleNamespace())

            assert message.answer.await_count == 3
            first = message.answer.await_args_list[0].args[0]
            second = message.answer.await_args_list[1].args[0]
            third = message.answer.await_args_list[2].args[0]
            assert "➖" in first and "10 000 сум" in first
            assert "➖" in second and "5 000 сум" in second
            assert "➕" in third and "50 000 сум" in third


class TestAmbiguousTypeQuestion:
    async def test_ambiguous_sends_question_no_transaction(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_003_001)
            wallet = make_wallet(budget, name="Карта сум")
            events = ExpenseCategory(family_budget_id=budget.id, name="События и тои")
            session.add_all([wallet, events])
            await session.flush()
            gifts = ExpenseCategory(
                family_budget_id=budget.id, name="Подарки", parent_id=events.id
            )
            session.add(gifts)
            user.default_wallet_id = wallet.id
            await session.flush()

            text = "подарок 500 тысяч"
            set_parser_override(
                StubParser(
                    responses={
                        text: ParseResponse(
                            operations=[
                                ParsedOperation(
                                    type="ambiguous",
                                    amount=500_000,
                                    currency="UZS",
                                    wallet_hint=None,
                                    category="Подарки",
                                    comment=None,
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

            message.answer.assert_awaited_once()
            body = message.answer.await_args.args[0]
            assert "**500 000 сум** · Подарки" in body
            assert MSG_TYPE_QUESTION in body
            kb = message.answer.await_args.kwargs["reply_markup"]
            assert kb.inline_keyboard[0][0].text == "Потратил"

            txns = (
                await session.scalars(select(Transaction).where(Transaction.family_budget_id == budget.id))
            ).all()
            assert txns == []

            pending = (
                await session.scalars(
                    select(QuickEntryPending).where(
                        QuickEntryPending.family_budget_id == budget.id
                    )
                )
            ).all()
            assert len(pending) == 1
            assert pending[0].charge_on_confirm is True

            await session.refresh(budget)
            assert budget.daily_model_calls == 0

    async def test_ambiguous_type_tap_spends_one_model_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_003_003)
            wallet = make_wallet(budget, name="Карта сум")
            events = ExpenseCategory(family_budget_id=budget.id, name="События и тои")
            session.add_all([wallet, events])
            await session.flush()
            gifts = ExpenseCategory(
                family_budget_id=budget.id, name="Подарки", parent_id=events.id
            )
            session.add(gifts)
            user.default_wallet_id = wallet.id
            await session.flush()

            text = "подарок 500 тысяч"
            set_parser_override(
                StubParser(
                    responses={
                        text: ParseResponse(
                            operations=[
                                ParsedOperation(
                                    type="ambiguous",
                                    amount=500_000,
                                    currency="UZS",
                                    wallet_hint=None,
                                    category="Подарки",
                                    comment=None,
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

            pending = (
                await session.scalars(
                    select(QuickEntryPending).where(
                        QuickEntryPending.family_budget_id == budget.id
                    )
                )
            ).one()
            await session.refresh(budget)
            assert budget.daily_model_calls == 0

            callback = make_callback(
                telegram_id=user.telegram_id,
                data=f"qe:type:{pending.id}:expense",
                message_text=f"**500 000 сум** · Подарки\n{MSG_TYPE_QUESTION}",
            )
            await handle_quick_entry_type(callback, SimpleNamespace())

            await session.refresh(budget)
            assert budget.daily_model_calls == 1


class TestMixedClearAndAmbiguous:
    async def test_mixed_sends_cards_then_question_and_spends_one_model_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_003_002)
            wallet = make_wallet(budget, name="Карта сум")
            events = ExpenseCategory(family_budget_id=budget.id, name="События и тои")
            food = ExpenseCategory(family_budget_id=budget.id, name="Еда")
            session.add_all([wallet, events, food])
            await session.flush()
            gifts = ExpenseCategory(
                family_budget_id=budget.id, name="Подарки", parent_id=events.id
            )
            groceries = ExpenseCategory(
                family_budget_id=budget.id, name="Продукты", parent_id=food.id
            )
            session.add_all([gifts, groceries])
            user.default_wallet_id = wallet.id
            await session.flush()

            text = "продукты 10 тысяч и подарок 500 тысяч"
            set_parser_override(
                StubParser(
                    responses={
                        text: ParseResponse(
                            operations=[
                                ParsedOperation(
                                    type="expense",
                                    amount=10_000,
                                    currency="UZS",
                                    wallet_hint=None,
                                    category="Продукты",
                                    comment=None,
                                ),
                                ParsedOperation(
                                    type="ambiguous",
                                    amount=500_000,
                                    currency="UZS",
                                    wallet_hint=None,
                                    category="Подарки",
                                    comment=None,
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

            message = make_message(telegram_id=user.telegram_id, text=text)
            await handle_quick_entry_text(message, SimpleNamespace())

            assert message.answer.await_count == 2
            card_text = message.answer.await_args_list[0].args[0]
            question_text = message.answer.await_args_list[1].args[0]
            assert "➖" in card_text and "10 000 сум" in card_text
            assert "**500 000 сум** · Подарки" in question_text
            assert MSG_TYPE_QUESTION in question_text

            txns = (
                await session.scalars(
                    select(Transaction).where(Transaction.family_budget_id == budget.id)
                )
            ).all()
            assert len(txns) == 1

            pending = (
                await session.scalars(
                    select(QuickEntryPending).where(
                        QuickEntryPending.family_budget_id == budget.id
                    )
                )
            ).all()
            assert len(pending) == 1
            assert pending[0].charge_on_confirm is False

            await session.refresh(budget)
            assert budget.daily_model_calls == 1

    async def test_mixed_type_tap_does_not_double_spend(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_003_004)
            wallet = make_wallet(budget, name="Карта сум")
            events = ExpenseCategory(family_budget_id=budget.id, name="События и тои")
            food = ExpenseCategory(family_budget_id=budget.id, name="Еда")
            session.add_all([wallet, events, food])
            await session.flush()
            gifts = ExpenseCategory(
                family_budget_id=budget.id, name="Подарки", parent_id=events.id
            )
            groceries = ExpenseCategory(
                family_budget_id=budget.id, name="Продукты", parent_id=food.id
            )
            session.add_all([gifts, groceries])
            user.default_wallet_id = wallet.id
            await session.flush()

            text = "продукты 10 тысяч и подарок 500 тысяч"
            set_parser_override(
                StubParser(
                    responses={
                        text: ParseResponse(
                            operations=[
                                ParsedOperation(
                                    type="expense",
                                    amount=10_000,
                                    currency="UZS",
                                    wallet_hint=None,
                                    category="Продукты",
                                    comment=None,
                                ),
                                ParsedOperation(
                                    type="ambiguous",
                                    amount=500_000,
                                    currency="UZS",
                                    wallet_hint=None,
                                    category="Подарки",
                                    comment=None,
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

            message = make_message(telegram_id=user.telegram_id, text=text)
            await handle_quick_entry_text(message, SimpleNamespace())

            pending = (
                await session.scalars(
                    select(QuickEntryPending).where(
                        QuickEntryPending.family_budget_id == budget.id
                    )
                )
            ).one()
            await session.refresh(budget)
            assert budget.daily_model_calls == 1

            callback = make_callback(
                telegram_id=user.telegram_id,
                data=f"qe:type:{pending.id}:expense",
                message_text=f"**500 000 сум** · Подарки\n{MSG_TYPE_QUESTION}",
            )
            await handle_quick_entry_type(callback, SimpleNamespace())

            await session.refresh(budget)
            assert budget.daily_model_calls == 1


class TestCurrencyMissing:
    async def test_currency_missing_section_7_4(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_004_001)
            wallet = make_wallet(budget, name="Карта сум", currency="UZS")
            session.add(wallet)
            user.default_wallet_id = wallet.id
            await session.flush()

            text = "usd expense"
            set_parser_override(
                StubParser(
                    responses={
                        text: ParseResponse(
                            operations=[
                                ParsedOperation(
                                    type="expense",
                                    amount=10,
                                    currency="USD",
                                    wallet_hint=None,
                                    category=None,
                                    comment=None,
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

            message.answer.assert_awaited_once_with(currency_missing_text("USD"))


class TestMessageLength:
    async def test_too_long_does_not_call_parser(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_005_001)
            wallet = make_wallet(budget, name="Карта сум")
            session.add(wallet)
            user.default_wallet_id = wallet.id
            await session.flush()

            spy = AsyncMock(side_effect=ParserUnavailable("should not be called"))
            set_parser_override(spy)
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            long_text = "x" * 501
            message = make_message(telegram_id=user.telegram_id, text=long_text)
            await handle_quick_entry_text(message, SimpleNamespace())

            spy.parse.assert_not_awaited()
            message.answer.assert_awaited_once_with(MSG_TOO_LONG)
            await session.refresh(budget)
            assert budget.daily_model_calls == 0
            assert budget.daily_unparsed == 0


class TestTooManyOperations:
    async def test_more_than_five_ops_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_006_001)
            wallet = make_wallet(budget, name="Карта сум")
            session.add(wallet)
            user.default_wallet_id = wallet.id
            await session.flush()

            ops = [
                ParsedOperation(
                    type="expense",
                    amount=1_000,
                    currency="UZS",
                    wallet_hint=None,
                    category=None,
                    comment=None,
                )
                for _ in range(6)
            ]
            text = "шесть операций"
            set_parser_override(StubParser(responses={text: ParseResponse(operations=ops)}))
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            message = make_message(telegram_id=user.telegram_id, text=text)
            await handle_quick_entry_text(message, SimpleNamespace())

            message.answer.assert_awaited_once_with(MSG_TOO_MANY_OPS)
            txns = (
                await session.scalars(select(Transaction).where(Transaction.family_budget_id == budget.id))
            ).all()
            assert txns == []


class TestModelFailure:
    async def test_section_7_11_does_not_increment_unparsed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_007_001)
            wallet = make_wallet(budget, name="Карта сум")
            session.add(wallet)
            user.default_wallet_id = wallet.id
            await session.flush()

            set_parser_override(StubParser())
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            class FailingParser:
                async def parse(self, request: object) -> ParseResponse:
                    raise ParserUnavailable("down")

            set_parser_override(FailingParser())

            message = make_message(telegram_id=user.telegram_id, text="такси 25 тысяч")
            await handle_quick_entry_text(message, SimpleNamespace())

            message.answer.assert_awaited_once_with(MSG_MODEL_FAIL)
            await session.refresh(budget)
            assert budget.daily_unparsed == 0
            assert budget.daily_model_calls == 0

    async def test_parser_malformed_does_not_increment_unparsed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_007_002)
            wallet = make_wallet(budget, name="Карта сум")
            session.add(wallet)
            user.default_wallet_id = wallet.id
            await session.flush()

            class MalformedParser:
                async def parse(self, request: object) -> ParseResponse:
                    raise ParserMalformed("bad json")

            set_parser_override(MalformedParser())
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            message = make_message(telegram_id=user.telegram_id, text="такси 25 тысяч")
            await handle_quick_entry_text(message, SimpleNamespace())

            message.answer.assert_awaited_once_with(MSG_MODEL_FAIL)
            await session.refresh(budget)
            assert budget.daily_unparsed == 0
            assert budget.daily_model_calls == 0


class TestWalletNameLeak:
    async def test_member_b_parse_request_excludes_member_a_personal_wallet(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            member_a, budget = await create_user(session, telegram_id=9_008_001)
            member_b, _ = await create_user(
                session, telegram_id=9_008_002, role="member", budget=budget
            )
            secret_name = f"A-personal-{uuid.uuid4().hex[:8]}"
            shared = make_wallet(budget, name="Shared wallet")
            personal_a = make_wallet(
                budget,
                name=secret_name,
                is_personal=True,
                owner_user_id=member_a.id,
            )
            session.add_all([shared, personal_a])
            member_b.default_wallet_id = shared.id
            await session.flush()

            captured: list[list[str]] = []

            class CapturingParser:
                async def parse(self, request: object) -> ParseResponse:
                    from app.parsing.types import ParseRequest

                    assert isinstance(request, ParseRequest)
                    captured.append(list(request.wallet_names))
                    return ParseResponse(operations=[])

            set_parser_override(CapturingParser())
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            message = make_message(telegram_id=member_b.telegram_id, text="что-то")
            await handle_quick_entry_text(message, SimpleNamespace())

            assert captured
            assert secret_name not in captured[0]
            assert "Shared wallet" in captured[0]
            message.answer.assert_awaited_once_with(MSG_NO_AMOUNT)
