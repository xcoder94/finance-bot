"""Regression tests for three bot-side defects:

1. Bot callbacks (`qe:del:`, `qe:ws:`) must apply the same permission rule
   the API uses (`require_transaction_modify_permission`) — a family member
   who does not own a personal wallet must not be able to delete or move a
   transaction that touches someone else's personal wallet, while shared
   wallet operations remain editable by any member (PRD 83, 89).
2. A message refused by the daily model-call limit must not grow
   `cascade_fallback_log` — only messages that actually reach the parser are
   logged.
3. The daily model-call limit ("check and consume") must be atomic under
   concurrency: at limit-1 remaining, N concurrent grant attempts must yield
   exactly one success and the counter must never exceed the limit.
"""

from __future__ import annotations

import asyncio
import socket
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import engine
from app.models.base import Base
from app.models.cascade_fallback_log import CascadeFallbackLog
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.parsing.stub import StubParser
from app.parsing.types import ParsedOperation, ParseResponse
from app.services.quick_entry_counters import (
    tashkent_today_for_counters,
    try_spend_model_call,
)
from bot.quick_entry.cards import wallet_set_callback_data
from bot.quick_entry.handlers import (
    handle_quick_entry_delete,
    handle_quick_entry_text,
    handle_quick_entry_wallet_set,
    set_parser_override,
)
from bot.quick_entry.texts import MSG_GONE

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


def make_callback(*, telegram_id: int, data: str) -> SimpleNamespace:
    message = SimpleNamespace(
        text="card",
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


def make_message(*, telegram_id: int, text: str) -> SimpleNamespace:
    return SimpleNamespace(
        from_user=SimpleNamespace(id=telegram_id),
        text=text,
        answer=AsyncMock(),
    )


async def seed_txn(
    session: AsyncSession,
    user: User,
    budget: FamilyBudget,
    *,
    wallet: Wallet,
    to_wallet: Wallet | None = None,
    amount: int = 25_000,
) -> Transaction:
    txn = Transaction(
        family_budget_id=budget.id,
        type="transfer" if to_wallet is not None else "expense",
        wallet_id=wallet.id,
        to_wallet_id=to_wallet.id if to_wallet is not None else None,
        amount=amount,
        to_amount=amount if to_wallet is not None else None,
        created_by_user_id=user.id,
        transaction_date=datetime(2026, 8, 1, 12, 0, tzinfo=TASHKENT),
    )
    session.add(txn)
    await session.flush()
    return txn


# Only the anyio marker applies to the whole module — the concurrency test
# class below runs against sqlite and must not be skipped when PostgreSQL is
# unavailable, unlike the permission/logging tests which need the real DB
# fixtures used elsewhere in this suite.
pytestmark = [pytest.mark.anyio]

requires_postgres = pytest.mark.skipif(
    not _db_available(), reason="PostgreSQL not available"
)


@pytest.fixture(autouse=True)
def reset_parser_override() -> AsyncIterator[None]:
    set_parser_override(None)
    yield
    set_parser_override(None)


@requires_postgres
class TestPersonalWalletDeletePermission:
    async def test_non_holder_member_cannot_delete(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            holder, budget = await create_user(session, telegram_id=9_500_001)
            other, _ = await create_user(
                session, telegram_id=9_500_002, role="member", budget=budget
            )
            personal = make_wallet(
                budget, name="Holder personal", is_personal=True, owner_user_id=holder.id
            )
            session.add(personal)
            await session.flush()
            txn = await seed_txn(session, holder, budget, wallet=personal)

            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )
            callback = make_callback(
                telegram_id=other.telegram_id, data=f"qe:del:{txn.id}"
            )
            await handle_quick_entry_delete(callback, SimpleNamespace())

            await session.refresh(txn)
            assert txn.is_deleted is False
            callback.answer.assert_awaited_once_with(MSG_GONE)
            callback.message.delete.assert_not_awaited()

    async def test_holder_can_delete(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async with rollback_session() as session:
            holder, budget = await create_user(session, telegram_id=9_500_003)
            personal = make_wallet(
                budget, name="Holder personal", is_personal=True, owner_user_id=holder.id
            )
            session.add(personal)
            await session.flush()
            txn = await seed_txn(session, holder, budget, wallet=personal)

            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )
            callback = make_callback(
                telegram_id=holder.telegram_id, data=f"qe:del:{txn.id}"
            )
            await handle_quick_entry_delete(callback, SimpleNamespace())

            await session.refresh(txn)
            assert txn.is_deleted is True
            callback.message.delete.assert_awaited_once()

    async def test_shared_wallet_deletable_by_any_member(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            owner, budget = await create_user(session, telegram_id=9_500_004)
            member, _ = await create_user(
                session, telegram_id=9_500_005, role="member", budget=budget
            )
            shared = make_wallet(budget, name="Shared wallet")
            session.add(shared)
            await session.flush()
            txn = await seed_txn(session, owner, budget, wallet=shared)

            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )
            callback = make_callback(
                telegram_id=member.telegram_id, data=f"qe:del:{txn.id}"
            )
            await handle_quick_entry_delete(callback, SimpleNamespace())

            await session.refresh(txn)
            assert txn.is_deleted is True
            callback.message.delete.assert_awaited_once()


@requires_postgres
class TestPersonalWalletChangeWalletPermission:
    async def test_non_holder_member_cannot_move(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            holder, budget = await create_user(session, telegram_id=9_500_101)
            other, _ = await create_user(
                session, telegram_id=9_500_102, role="member", budget=budget
            )
            personal = make_wallet(
                budget, name="Holder personal", is_personal=True, owner_user_id=holder.id
            )
            shared = make_wallet(budget, name="Shared wallet")
            session.add_all([personal, shared])
            await session.flush()
            txn = await seed_txn(session, holder, budget, wallet=personal)

            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )
            callback = make_callback(
                telegram_id=other.telegram_id,
                data=wallet_set_callback_data(txn.id, shared.id),
            )
            await handle_quick_entry_wallet_set(callback, SimpleNamespace())

            await session.refresh(txn)
            assert txn.wallet_id == personal.id
            callback.answer.assert_awaited_once_with(MSG_GONE)
            callback.message.edit_text.assert_not_awaited()

    async def test_holder_can_move(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async with rollback_session() as session:
            holder, budget = await create_user(session, telegram_id=9_500_103)
            personal = make_wallet(
                budget, name="Holder personal", is_personal=True, owner_user_id=holder.id
            )
            shared = make_wallet(budget, name="Shared wallet")
            session.add_all([personal, shared])
            await session.flush()
            txn = await seed_txn(session, holder, budget, wallet=personal)

            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )
            callback = make_callback(
                telegram_id=holder.telegram_id,
                data=wallet_set_callback_data(txn.id, shared.id),
            )
            await handle_quick_entry_wallet_set(callback, SimpleNamespace())

            await session.refresh(txn)
            assert txn.wallet_id == shared.id
            callback.message.edit_text.assert_awaited_once()


@requires_postgres
class TestFallbackLogOnLimit:
    async def test_refused_message_writes_no_log_row(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_500_201)
            wallet = make_wallet(budget, name="Наличный сум")
            session.add(wallet)
            await session.flush()
            user.default_wallet_id = wallet.id
            budget.counters_day = tashkent_today_for_counters()
            budget.daily_model_calls = 50  # DAILY_MODEL_CALL_LIMIT default
            await session.flush()

            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )
            set_parser_override(StubParser())

            message = make_message(telegram_id=user.telegram_id, text="что-то непонятное")
            await handle_quick_entry_text(message, SimpleNamespace())

            rows = (
                await session.scalars(
                    select(CascadeFallbackLog).where(
                        CascadeFallbackLog.family_budget_id == budget.id
                    )
                )
            ).all()
            assert rows == []

    async def test_accepted_message_still_writes_log_row(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_500_202)
            wallet = make_wallet(budget, name="Наличный сум")
            session.add(wallet)
            await session.flush()
            user.default_wallet_id = wallet.id
            await session.flush()

            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )
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
                                    category=None,
                                    comment=None,
                                )
                            ]
                        )
                    }
                )
            )

            message = make_message(telegram_id=user.telegram_id, text="такси 25 тысяч")
            await handle_quick_entry_text(message, SimpleNamespace())

            rows = (
                await session.scalars(
                    select(CascadeFallbackLog).where(
                        CascadeFallbackLog.family_budget_id == budget.id
                    )
                )
            ).all()
            assert len(rows) == 1


class TestModelCallGrantConcurrency:
    """Drives the real `try_spend_model_call` atomic grant through a real
    (sqlite) database against concurrent callers, following the pattern
    already used by tests/test_quick_entry_counters.py."""

    @pytest.fixture
    async def sqlite_session(self):
        # StaticPool + a shared cache URI keep every connection pointed at the
        # same in-memory database — needed because the concurrency test opens
        # one AsyncSession (and therefore one connection) per attempt, and a
        # bare sqlite in-memory URL gives each connection its own empty DB.
        engine_ = create_async_engine(
            "sqlite+aiosqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(engine_.sync_engine, "connect")
        def _fk(dbapi_connection, _):  # pragma: no cover - sqlite pragma plumbing
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        async with engine_.begin() as conn:
            await conn.run_sync(
                Base.metadata.create_all,
                tables=[FamilyBudget.__table__],
            )

        async with AsyncSession(engine_, expire_on_commit=False) as session:
            yield session

        await engine_.dispose()

    async def test_only_one_grant_succeeds_at_the_limit(self, sqlite_session) -> None:
        limit = 50
        budget = FamilyBudget(daily_model_calls=limit - 1)
        sqlite_session.add(budget)
        await sqlite_session.commit()
        await sqlite_session.refresh(budget)

        budget_id = budget.id
        engine_ = sqlite_session.bind

        # Each concurrent attempt uses its own session/connection against the
        # same sqlite database file (shared in-memory via the engine's pool),
        # exactly like independent concurrent requests would.
        async def grant_attempt() -> bool:
            async with AsyncSession(engine_, expire_on_commit=False) as s:
                b = await s.get(FamilyBudget, budget_id)
                granted = await try_spend_model_call(s, b, limit)
                await s.commit()
                return granted

        results = await asyncio.gather(*[grant_attempt() for _ in range(10)])

        assert results.count(True) == 1
        assert results.count(False) == 9

        async with AsyncSession(engine_, expire_on_commit=False) as verify:
            final = await verify.get(FamilyBudget, budget_id)
            assert final.daily_model_calls == limit
