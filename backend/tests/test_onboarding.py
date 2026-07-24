import asyncio
import socket
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.user import User
from app.models.wallet import Wallet
from bot.onboarding import (
    MESSAGES,
    SEED_EXPENSE_CATEGORIES,
    SEED_WALLETS,
    copy_seed_data,
    count_seed_rows,
    get_active_user_by_telegram_id,
    get_family_budget_by_invite_token,
    invite_handler,
    language_callback,
    parse_start_payload,
)

EXPECTED_EXPENSE_SUBCATEGORY_COUNT = sum(
    len(subs) for _, subs in SEED_EXPENSE_CATEGORIES.values()
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
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await trans.rollback()
            await session.close()


pytestmark = pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")


class TestParseStartPayload:
    @pytest.mark.parametrize(
        ("payload", "expected_flow", "expected_token"),
        [
            (None, "owner", None),
            ("", "owner", None),
            ("garbage", "owner", None),
            ("invite_abc123", "member", "abc123"),
        ],
    )
    def test_parse_start_payload(
        self, payload: str | None, expected_flow: str, expected_token: str | None
    ) -> None:
        flow, token = parse_start_payload(payload)
        assert flow == expected_flow
        assert token == expected_token


class TestInviteTokenLookup:
    def test_valid_and_invalid_invite_token_lookup(self) -> None:
        async def _run() -> None:
            token = f"test-token-lookup-{uuid.uuid4()}"
            async with rollback_session() as session:
                budget = FamilyBudget(invite_token=token)
                session.add(budget)
                await session.flush()

                found = await get_family_budget_by_invite_token(session, token)
                assert found is not None
                assert found.invite_token == token

                missing = await get_family_budget_by_invite_token(session, "nonexistent-token")
                assert missing is None

        asyncio.run(_run())


class TestAlreadyRegisteredShortCircuit:
    def test_get_active_user_returns_none_when_soft_deleted(self) -> None:
        async def _run() -> None:
            telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
            async with rollback_session() as session:
                budget = FamilyBudget(invite_token=f"short-circuit-{uuid.uuid4()}")
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

                active = await get_active_user_by_telegram_id(session, telegram_id)
                assert active is not None
                assert active.language == "ru"

                user.is_deleted = True
                await session.flush()

                assert await get_active_user_by_telegram_id(session, telegram_id) is None

        asyncio.run(_run())


class TestLanguageCallbackSessionOrdering:
    def test_owner_welcome_does_not_resolve_bot_username(self) -> None:
        async def _run() -> None:
            session = SimpleNamespace(
                add=lambda _model: None,
                flush=AsyncMock(),
            )

            class TransactionContext:
                async def __aenter__(self) -> None:
                    return None

                async def __aexit__(self, *_args: object) -> None:
                    return None

            session.begin = lambda: TransactionContext()

            class SessionContext:
                async def __aenter__(self) -> SimpleNamespace:
                    return session

                async def __aexit__(self, *_args: object) -> None:
                    return None

            message = SimpleNamespace(answer=AsyncMock(), delete=AsyncMock())
            callback = SimpleNamespace(
                from_user=SimpleNamespace(id=123),
                message=message,
                data="lang:ru",
                answer=AsyncMock(),
            )
            state = SimpleNamespace(
                get_data=AsyncMock(
                    return_value={
                        "flow": "owner",
                        "telegram_id": 123,
                        "first_name": "Test",
                        "username": "tester",
                    }
                ),
                clear=AsyncMock(),
            )
            bot = SimpleNamespace(get_me=AsyncMock())

            with (
                patch(
                    "bot.onboarding.async_session_factory",
                    return_value=SessionContext(),
                ),
                patch(
                    "bot.onboarding.get_active_user_by_telegram_id",
                    new=AsyncMock(return_value=None),
                ),
                patch("bot.onboarding.copy_seed_data", new=AsyncMock()),
            ):
                await language_callback(callback, state, bot)

            bot.get_me.assert_not_awaited()
            message.answer.assert_awaited_once()
            answer_args, answer_kwargs = message.answer.await_args
            assert answer_args[0] == MESSAGES["welcome_owner"]["ru"]
            assert "reply_markup" in answer_kwargs
            message.delete.assert_awaited_once()

        asyncio.run(_run())


class TestInviteHandlerSessionOrdering:
    def test_bot_lookup_happens_after_session_closes(self) -> None:
        async def _run() -> None:
            session_open = False
            session = AsyncMock()
            budget = SimpleNamespace(
                is_deleted=False,
                invite_token="invite-token",
            )
            session.get.return_value = budget
            user = SimpleNamespace(
                role="owner",
                language="ru",
                family_budget_id=uuid.uuid4(),
            )

            class SessionContext:
                async def __aenter__(self) -> AsyncMock:
                    nonlocal session_open
                    session_open = True
                    return session

                async def __aexit__(self, *_args: object) -> None:
                    nonlocal session_open
                    session_open = False

            def session_factory() -> SessionContext:
                return SessionContext()

            async def get_me() -> SimpleNamespace:
                assert session_open is False
                return SimpleNamespace(username="finance_test_bot")

            message = SimpleNamespace(
                from_user=SimpleNamespace(id=123),
                answer=AsyncMock(),
            )
            bot = SimpleNamespace(get_me=AsyncMock(side_effect=get_me))

            with patch("bot.onboarding.async_session_factory", session_factory):
                with patch(
                    "bot.onboarding.get_active_user_by_telegram_id",
                    new=AsyncMock(return_value=user),
                ):
                    with patch("app.services.invite._bot_username", None):
                        await invite_handler(message, bot)

            bot.get_me.assert_awaited_once()
            message.answer.assert_awaited_once_with(
                "https://t.me/finance_test_bot?start=invite_invite-token"
            )

        asyncio.run(_run())


class TestSeedDataCopy:
    def test_seed_data_counts_and_parent_linkage(self) -> None:
        async def _run() -> None:
            async with rollback_session() as session:
                budget = FamilyBudget(invite_token=f"seed-copy-{uuid.uuid4()}")
                session.add(budget)
                await session.flush()
                budget_id = budget.id
                await copy_seed_data(session, budget_id)

                counts = await count_seed_rows(session, budget_id)
                assert counts["wallets"] == 4
                assert counts["income_categories"] == 4
                assert counts["expense_top_level"] == 5
                assert counts["expense_subcategories"] == EXPECTED_EXPENSE_SUBCATEGORY_COUNT

                wallet_stmt = select(Wallet).where(
                    Wallet.family_budget_id == budget_id,
                    Wallet.is_deleted.is_(False),
                )
                wallets = (await session.scalars(wallet_stmt)).all()
                assert {(w.name, w.currency) for w in wallets} == {
                    (name, currency) for name, currency, _ in SEED_WALLETS
                }
                assert {w.translation_key for w in wallets} == {
                    key for _, _, key in SEED_WALLETS
                }

                stmt = select(ExpenseCategory).where(
                    ExpenseCategory.family_budget_id == budget_id,
                    ExpenseCategory.parent_id.is_not(None),
                )
                subcategories = (await session.scalars(stmt)).all()
                assert subcategories
                for sub in subcategories:
                    parent = await session.get(ExpenseCategory, sub.parent_id)
                    assert parent is not None
                    assert parent.parent_id is None
                    assert parent.family_budget_id == budget_id

        asyncio.run(_run())
