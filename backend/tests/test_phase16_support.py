"""Phase 16 Task D — support message relay."""

from __future__ import annotations

import socket
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine
from app.models.family_budget import FamilyBudget
from app.models.support_message import SupportMessage
from app.models.user import User
from bot.support import (
    CALLBACK_QUICK_PREFIX,
    STRINGS,
    SupportStates,
    build_main_reply_keyboard,
    build_support_header,
    relay_to_support,
    support_entry,
    support_entry_label,
    support_free_text,
    support_inbound_reply,
    support_options_keyboard,
    support_own_question,
    support_quick_option,
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


class SessionFactory:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def __call__(self) -> SessionFactory:
        return self

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *_args: object) -> None:
        return None


async def _create_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    language: str = "ru",
) -> tuple[User, FamilyBudget]:
    budget = FamilyBudget(invite_token=f"test-{uuid.uuid4()}", name="Семья Тестовых")
    session.add(budget)
    await session.flush()
    user = User(
        telegram_id=telegram_id,
        family_budget_id=budget.id,
        role="owner",
        language=language,
    )
    session.add(user)
    await session.flush()
    return user, budget


def _tid() -> int:
    return int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000


def test_support_message_columns_exist() -> None:
    cols = {c.name for c in SupportMessage.__table__.columns}
    assert cols == {
        "id",
        "forwarded_message_id",
        "telegram_user_id",
        "family_budget_id",
        "created_at",
    }


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_support_messages_table_exists() -> None:
    await _reset_engine()
    async with engine.connect() as conn:
        def check(sync_conn):
            tables = inspect(sync_conn).get_table_names()
            assert "support_messages" in tables
            cols = {
                c["name"]: c
                for c in inspect(sync_conn).get_columns("support_messages")
            }
            assert cols["forwarded_message_id"]["nullable"] is False
            assert cols["telegram_user_id"]["nullable"] is False
            assert cols["family_budget_id"]["nullable"] is False

        await conn.run_sync(check)


def test_support_entry_label_verbatim() -> None:
    assert support_entry_label("ru") == "Написать в поддержку"
    assert support_entry_label("uz") == "Qo'llab-quvvatlashga yozish"


def test_build_support_header_with_and_without_username() -> None:
    assert (
        build_support_header("Семья Каримовых", "Дилноза", "dilnoza_uz")
        == "Семья Каримовых — Дилноза (@dilnoza_uz)"
    )
    assert build_support_header("Семья Каримовых", "Дилноза", None) == (
        "Семья Каримовых — Дилноза"
    )


def test_keyboard_none_when_support_unset(monkeypatch) -> None:
    monkeypatch.setattr("bot.support.SUPPORT_CHAT_ID", None)
    assert build_main_reply_keyboard("ru") is None


def test_keyboard_has_support_when_set(monkeypatch) -> None:
    monkeypatch.setattr("bot.support.SUPPORT_CHAT_ID", "-100123")
    kb = build_main_reply_keyboard("uz")
    assert kb is not None
    assert len(kb.keyboard) == 1
    assert kb.keyboard[0][0].text == support_entry_label("uz")


def test_keyboard_never_carries_web_app_launcher(monkeypatch) -> None:
    monkeypatch.setattr("bot.support.SUPPORT_CHAT_ID", "-100123")
    kb = build_main_reply_keyboard("ru")
    assert kb is not None
    assert len(kb.keyboard) == 1
    assert kb.keyboard[0][0].text == support_entry_label("ru")
    assert all(
        button.web_app is None for row in kb.keyboard for button in row
    )


def test_keyboard_none_when_both_unset(monkeypatch) -> None:
    monkeypatch.setattr("bot.support.SUPPORT_CHAT_ID", None)
    assert build_main_reply_keyboard() is None


def test_support_options_keyboard_ru() -> None:
    kb = support_options_keyboard("ru")
    labels = [row[0].text for row in kb.inline_keyboard]
    assert labels == [
        STRINGS["quick_1"]["ru"],
        STRINGS["quick_2"]["ru"],
        STRINGS["quick_3"]["ru"],
        STRINGS["quick_4"]["ru"],
        STRINGS["write_own"]["ru"],
    ]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
class TestSupportHandlers:
    @pytest.mark.anyio
    async def test_support_entry_shows_options(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("bot.support.SUPPORT_CHAT_ID", "-100999")
        async with rollback_session() as session:
            user, _budget = await _create_user(session, telegram_id=_tid())
            monkeypatch.setattr(
                "bot.support.async_session_factory",
                SessionFactory(session),
            )

            message = SimpleNamespace(
                from_user=SimpleNamespace(id=user.telegram_id),
                answer=AsyncMock(),
            )
            state = SimpleNamespace(clear=AsyncMock())

            await support_entry(message, state)

            state.clear.assert_awaited_once()
            message.answer.assert_awaited_once()
            _, kwargs = message.answer.await_args
            assert len(kwargs["reply_markup"].inline_keyboard) == 5

    @pytest.mark.anyio
    async def test_support_entry_noop_when_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("bot.support.SUPPORT_CHAT_ID", None)
        async with rollback_session() as session:
            user, _budget = await _create_user(session, telegram_id=_tid())
            monkeypatch.setattr(
                "bot.support.async_session_factory",
                SessionFactory(session),
            )

            message = SimpleNamespace(
                from_user=SimpleNamespace(id=user.telegram_id),
                answer=AsyncMock(),
            )
            state = SimpleNamespace(clear=AsyncMock())

            await support_entry(message, state)
            message.answer.assert_not_awaited()

    @pytest.mark.anyio
    async def test_quick_option_relays_and_confirms(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("bot.support.SUPPORT_CHAT_ID", "-100999")
        async with rollback_session() as session:
            user, budget = await _create_user(session, telegram_id=_tid())
            monkeypatch.setattr(
                "bot.support.async_session_factory",
                SessionFactory(session),
            )

            bot = AsyncMock()
            bot.send_message = AsyncMock(
                return_value=SimpleNamespace(message_id=42)
            )
            callback = SimpleNamespace(
                from_user=SimpleNamespace(
                    id=user.telegram_id, first_name="Али", username="ali_test"
                ),
                message=SimpleNamespace(
                    edit_reply_markup=AsyncMock(),
                    answer=AsyncMock(),
                ),
                data=f"{CALLBACK_QUICK_PREFIX}0",
                answer=AsyncMock(),
            )

            await support_quick_option(callback, bot)

            bot.send_message.assert_awaited_once()
            body = bot.send_message.await_args.kwargs["text"]
            assert body.startswith("Семья Тестовых — Али (@ali_test)\n\n")
            assert body.endswith(STRINGS["quick_1"]["ru"])

            row = await session.scalar(
                select(SupportMessage).where(
                    SupportMessage.forwarded_message_id == 42
                )
            )
            assert row is not None
            assert row.telegram_user_id == user.telegram_id
            assert row.family_budget_id == budget.id

            callback.message.answer.assert_awaited_once_with(
                STRINGS["confirmation"]["ru"]
            )

    @pytest.mark.anyio
    async def test_own_question_prompt_then_relay(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("bot.support.SUPPORT_CHAT_ID", "-100999")
        async with rollback_session() as session:
            user, _budget = await _create_user(
                session, telegram_id=_tid(), language="uz"
            )
            monkeypatch.setattr(
                "bot.support.async_session_factory",
                SessionFactory(session),
            )

            callback = SimpleNamespace(
                from_user=SimpleNamespace(id=user.telegram_id),
                message=SimpleNamespace(
                    edit_reply_markup=AsyncMock(),
                    answer=AsyncMock(),
                ),
                answer=AsyncMock(),
            )
            state = SimpleNamespace(set_state=AsyncMock())

            await support_own_question(callback, state)
            state.set_state.assert_awaited_once_with(
                SupportStates.awaiting_free_text
            )
            callback.message.answer.assert_awaited_once_with(
                STRINGS["free_text_prompt"]["uz"]
            )

            bot = AsyncMock()
            bot.send_message = AsyncMock(
                return_value=SimpleNamespace(message_id=77)
            )
            message = SimpleNamespace(
                from_user=SimpleNamespace(
                    id=user.telegram_id, first_name="User", username=None
                ),
                text="Savol matni",
                answer=AsyncMock(),
            )
            state2 = SimpleNamespace(clear=AsyncMock())

            await support_free_text(message, state2, bot)

            bot.send_message.assert_awaited_once()
            assert "Savol matni" in bot.send_message.await_args.kwargs["text"]
            row = await session.scalar(
                select(SupportMessage).where(
                    SupportMessage.forwarded_message_id == 77
                )
            )
            assert row is not None
            message.answer.assert_awaited_once_with(
                STRINGS["confirmation"]["uz"]
            )

    @pytest.mark.anyio
    async def test_inbound_reply_dm_unchanged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("bot.support.SUPPORT_CHAT_ID", "-100999")
        async with rollback_session() as session:
            user, budget = await _create_user(session, telegram_id=_tid())
            session.add(
                SupportMessage(
                    forwarded_message_id=555,
                    telegram_user_id=user.telegram_id,
                    family_budget_id=budget.id,
                )
            )
            await session.flush()
            monkeypatch.setattr(
                "bot.support.async_session_factory",
                SessionFactory(session),
            )

            bot = AsyncMock()
            message = SimpleNamespace(
                chat=SimpleNamespace(id=-100999),
                reply_to_message=SimpleNamespace(message_id=555),
                text="Ответ поддержки без изменений",
            )

            await support_inbound_reply(message, bot)

            bot.send_message.assert_awaited_once_with(
                user.telegram_id, "Ответ поддержки без изменений"
            )

    @pytest.mark.anyio
    async def test_inbound_reply_no_mapping_silent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("bot.support.SUPPORT_CHAT_ID", "-100999")
        async with rollback_session() as session:
            monkeypatch.setattr(
                "bot.support.async_session_factory",
                SessionFactory(session),
            )

            bot = AsyncMock()
            message = SimpleNamespace(
                chat=SimpleNamespace(id=-100999),
                reply_to_message=SimpleNamespace(message_id=99999),
                text="Нет маппинга",
            )

            await support_inbound_reply(message, bot)
            bot.send_message.assert_not_awaited()


def test_inbound_ignored_for_non_support_chat(monkeypatch) -> None:
    from bot.support import _is_support_chat

    monkeypatch.setattr("bot.support.SUPPORT_CHAT_ID", "-100999")
    message = SimpleNamespace(chat=SimpleNamespace(id=12345))
    assert _is_support_chat(message) is False
    message_support = SimpleNamespace(chat=SimpleNamespace(id=-100999))
    assert _is_support_chat(message_support) is True


@pytest.mark.anyio
async def test_relay_to_support_calls_bot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("bot.support.SUPPORT_CHAT_ID", "-100888")
    bot = AsyncMock()
    bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=11))
    msg_id = await relay_to_support(bot, header="Header", text="Body")
    assert msg_id == 11
    bot.send_message.assert_awaited_once_with(
        chat_id=-100888, text="Header\n\nBody"
    )


def test_support_router_before_quick_entry() -> None:
    import bot.main as bot_main

    with open(bot_main.__file__, encoding="utf-8") as f:
        content = f.read()
    support_pos = content.index("support_router")
    quick_pos = content.index("quick_entry_router")
    assert support_pos < quick_pos
