import socket
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import DAILY_MODEL_CALL_LIMIT
from app.db import engine
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.parsing.stub import StubParser
from app.parsing.types import ParseResponse, ParsedOperation
from app.services.quick_entry_counters import tashkent_today_for_counters
from bot.quick_entry.handlers import handle_quick_entry_text, set_parser_override
from bot.quick_entry.texts import model_limit_text


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
) -> tuple[User, FamilyBudget]:
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


def make_wallet(budget: FamilyBudget, *, name: str, currency: str = "UZS") -> Wallet:
    return Wallet(
        family_budget_id=budget.id,
        name=name,
        currency=currency,
        is_personal=False,
    )


def make_message(*, telegram_id: int, text: str) -> SimpleNamespace:
    return SimpleNamespace(
        from_user=SimpleNamespace(id=telegram_id),
        text=text,
        answer=AsyncMock(),
    )


def _exhaust_model_limit(budget: FamilyBudget) -> None:
    budget.counters_day = tashkent_today_for_counters()
    budget.daily_model_calls = DAILY_MODEL_CALL_LIMIT


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
    transport = ExpenseCategory(
        family_budget_id=budget.id,
        name="Транспорт",
        translation_key="transport",
    )
    session.add_all([wallet, transport])
    await session.flush()
    taxi = ExpenseCategory(
        family_budget_id=budget.id,
        name="Такси",
        parent_id=transport.id,
        translation_key="taxi",
    )
    session.add(taxi)
    user.default_wallet_id = wallet.id
    await session.flush()
    return wallet, taxi


class FailingParser(StubParser):
    async def parse(self, request):  # type: ignore[no-untyped-def]
        pytest.fail("parser.parse must not be called on prefilter hit")


pytestmark = [
    pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available"),
    pytest.mark.anyio,
]


@pytest.fixture(autouse=True)
def reset_parser_override() -> AsyncIterator[None]:
    set_parser_override(None)
    yield
    set_parser_override(None)


class TestPrefilterHandlerWiring:
    async def test_prefilter_hit_skips_parser_and_model_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_101_001)
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
            _exhaust_model_limit(budget)
            await session.flush()

            set_parser_override(FailingParser())
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            message = make_message(telegram_id=user.telegram_id, text="такси 25 тысяч")
            await handle_quick_entry_text(message, SimpleNamespace())

            message.answer.assert_awaited_once()
            card_text = message.answer.await_args.args[0]
            assert "25 000 сум" in card_text
            assert "Такси" in card_text
            assert budget.daily_model_calls == DAILY_MODEL_CALL_LIMIT

    async def test_prefilter_miss_calls_parser(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_101_002)
            wallet, _ = await seed_taxi_setup(session, user, budget)
            user.default_wallet_id = wallet.id
            await session.flush()

            parser = StubParser(
                responses={
                    "непонятный текст 10000": ParseResponse(
                        operations=[
                            ParsedOperation(
                                type="expense",
                                amount=10_000,
                                currency="UZS",
                                wallet_hint=None,
                                category="Такси",
                                comment=None,
                            )
                        ]
                    )
                }
            )
            set_parser_override(parser)
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            message = make_message(
                telegram_id=user.telegram_id, text="непонятный текст 10000"
            )
            await handle_quick_entry_text(message, SimpleNamespace())

            message.answer.assert_awaited_once()
            assert budget.daily_model_calls == 1

    async def test_prefilter_hit_when_model_limit_exhausted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_101_003)
            wallet, _ = await seed_taxi_setup(session, user, budget)
            user.default_wallet_id = wallet.id
            _exhaust_model_limit(budget)
            await session.flush()

            set_parser_override(FailingParser())
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            message = make_message(telegram_id=user.telegram_id, text="такси 25 тысяч")
            await handle_quick_entry_text(message, SimpleNamespace())

            message.answer.assert_awaited_once()
            assert model_limit_text(DAILY_MODEL_CALL_LIMIT) not in (
                message.answer.await_args.args[0]
            )

    async def test_fall_through_respects_model_limit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_101_004)
            wallet, _ = await seed_taxi_setup(session, user, budget)
            user.default_wallet_id = wallet.id
            _exhaust_model_limit(budget)
            await session.flush()

            set_parser_override(StubParser())
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            message = make_message(telegram_id=user.telegram_id, text="такси")
            await handle_quick_entry_text(message, SimpleNamespace())

            message.answer.assert_awaited_once()
            assert message.answer.await_args.args[0] == model_limit_text(
                DAILY_MODEL_CALL_LIMIT
            )
