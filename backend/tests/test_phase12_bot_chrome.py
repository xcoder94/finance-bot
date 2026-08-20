"""Phase 12 — bot chrome outside quick entry."""

from __future__ import annotations

import asyncio
import inspect
import socket
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from aiogram.filters import Command
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from app.models.user import User
from app.services.member_texts import welcome_invited, welcome_solo
from app.services.release_announcement import (
    RELEASE_ANNOUNCEMENT_TEXT,
    send_release_announcements,
)
from tests.test_wallets_categories import api_client, create_user_with_budget
from bot.goals import router as goals_router
from bot.membership import router as membership_router
from bot.onboarding import (
    OPEN_APP_BUTTON_LABEL,
    language_callback,
    open_app_keyboard,
    router as onboarding_router,
)
from bot.quick_entry.handlers import router as quick_entry_router


START_SOLO_TEXT = (
    "Chontak — семейный бюджет.\n"
    "\n"
    "Записывайте траты прямо здесь, сообщением:\n"
    "`такси 25 тысяч`\n"
    "\n"
    "Кошельки, категории и аналитика — в приложении."
)


def test_user_has_release_announcement_delivered_at_column() -> None:
    col = User.__table__.c.release_announcement_delivered_at
    assert col.nullable is True
    # column accepts datetime | None at ORM level
    assert "release_announcement_delivered_at" in User.__mapper__.columns


def test_welcome_solo_exact_18_1() -> None:
    assert welcome_solo() == START_SOLO_TEXT


def test_welcome_invited_18_2_regression_unchanged() -> None:
    text = welcome_invited("Семья Юсуповых")
    assert text == (
        "Вы присоединились к бюджету «Семья Юсуповых».\n"
        "Всё, что вы запишете, увидят остальные участники.\n"
        "\n"
        "Записывайте траты прямо здесь, сообщением:\n"
        "`такси 25 тысяч`\n"
        "\n"
        "Кошельки, цели и аналитика — в приложении."
    )


def test_open_app_button_label_exact() -> None:
    assert OPEN_APP_BUTTON_LABEL == "Открыть приложение"


def test_open_app_keyboard_single_button(monkeypatch) -> None:
    monkeypatch.setattr("bot.support.MINI_APP_URL", "https://example.test/app")
    monkeypatch.setattr("bot.support.SUPPORT_CHAT_ID", None)
    kb = open_app_keyboard()
    assert isinstance(kb, ReplyKeyboardMarkup)
    assert len(kb.keyboard) == 1
    assert len(kb.keyboard[0]) == 1
    btn = kb.keyboard[0][0]
    assert isinstance(btn, KeyboardButton)
    assert btn.text == "Открыть приложение"
    assert btn.web_app == WebAppInfo(url="https://example.test/app")
    assert kb.resize_keyboard is True
    assert kb.is_persistent is True


def test_open_app_keyboard_absent_when_url_missing(monkeypatch) -> None:
    monkeypatch.setattr("bot.support.MINI_APP_URL", None)
    monkeypatch.setattr("bot.support.SUPPORT_CHAT_ID", None)
    assert open_app_keyboard() is None


def test_menu_command_not_registered() -> None:
    routers = (
        onboarding_router,
        membership_router,
        goals_router,
        quick_entry_router,
    )
    for r in routers:
        for handler in r.message.handlers:
            for filt in handler.filters:
                callback = getattr(filt, "callback", filt)
                if isinstance(callback, Command):
                    commands = set(callback.commands)
                    assert "menu" not in commands


def test_owner_language_callback_sends_18_1_with_markdown_and_keyboard() -> None:
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
        fake_kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Открыть приложение")]],
            resize_keyboard=True,
            is_persistent=True,
        )

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
            patch("bot.onboarding.assign_default_card_uzs", new=AsyncMock()),
            patch("bot.onboarding.open_app_keyboard", return_value=fake_kb),
        ):
            await language_callback(callback, state, bot)

        message.answer.assert_awaited_once()
        args, kwargs = message.answer.await_args
        assert args[0] == START_SOLO_TEXT
        assert kwargs.get("parse_mode") == "Markdown"
        assert kwargs.get("reply_markup") is fake_kb

    asyncio.run(_run())


def test_invited_language_callback_keeps_18_2_and_uses_markdown() -> None:
    async def _run() -> None:
        session = SimpleNamespace(
            add=lambda _model: None,
            flush=AsyncMock(),
            execute=AsyncMock(),
            get=AsyncMock(
                return_value=SimpleNamespace(
                    name="Семья Юсуповых",
                    is_deleted=False,
                )
            ),
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
            from_user=SimpleNamespace(id=456),
            message=message,
            data="lang:ru",
            answer=AsyncMock(),
        )
        state = SimpleNamespace(
            get_data=AsyncMock(
                return_value={
                    "flow": "member",
                    "telegram_id": 456,
                    "family_budget_id": str(uuid.uuid4()),
                    "first_name": "New",
                    "username": "newbie",
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
            patch(
                "bot.onboarding.count_active_members",
                new=AsyncMock(return_value=1),
            ),
            patch("bot.onboarding.assign_default_card_uzs", new=AsyncMock()),
            patch("bot.onboarding.open_app_keyboard", return_value=None),
        ):
            await language_callback(callback, state, bot)

        args, kwargs = message.answer.await_args
        assert args[0] == welcome_invited("Семья Юсуповых")
        assert kwargs.get("parse_mode") == "Markdown"

    asyncio.run(_run())


ANNOUNCEMENT_TEXT = (
    "Теперь трату можно записать прямо здесь, сообщением.\n"
    "Напишите, например: `такси 25 тысяч`\n"
    "\n"
    "В приложении появились личные кошельки, цели и управление участниками."
)


def _db_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            return True
    except OSError:
        return False


def _tid() -> int:
    return int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000


async def _mark_prior_users_delivered(session: AsyncSession) -> None:
    """Exclude committed fixture users so only users created in-test are eligible."""
    await session.execute(
        update(User)
        .where(User.release_announcement_delivered_at.is_(None))
        .values(release_announcement_delivered_at=datetime.now(timezone.utc))
    )
    await session.commit()


def test_release_announcement_text_exact_18_4() -> None:
    assert RELEASE_ANNOUNCEMENT_TEXT == ANNOUNCEMENT_TEXT


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_announcement_sent_once_then_skipped(
    api_client: tuple[object, AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("bot.support.MINI_APP_URL", "https://example.test/app")
    monkeypatch.setattr("bot.support.SUPPORT_CHAT_ID", None)
    _, session = api_client
    await _mark_prior_users_delivered(session)
    tid = _tid()
    user, _budget = await create_user_with_budget(session, telegram_id=tid, role="owner")
    await session.commit()
    await session.refresh(user)

    cutoff = datetime.now(timezone.utc) + timedelta(hours=1)
    bot = AsyncMock()

    sent1 = await send_release_announcements(session, bot, cutoff, dry_run=False)
    assert sent1 == 1
    assert bot.send_message.await_count == 1
    call = bot.send_message.await_args
    assert call.args[0] == tid
    assert call.args[1] == ANNOUNCEMENT_TEXT
    assert call.kwargs.get("parse_mode") == "Markdown"
    markup = call.kwargs.get("reply_markup")
    assert markup is not None
    assert isinstance(markup, ReplyKeyboardMarkup)
    assert len(markup.keyboard) == 1
    assert len(markup.keyboard[0]) == 1
    assert markup.keyboard[0][0].text == OPEN_APP_BUTTON_LABEL
    await session.refresh(user)
    assert user.release_announcement_delivered_at is not None

    bot.reset_mock()
    sent2 = await send_release_announcements(session, bot, cutoff, dry_run=False)
    assert sent2 == 0
    bot.send_message.assert_not_awaited()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_user_created_after_cutoff_never_eligible(
    api_client: tuple[object, AsyncSession],
) -> None:
    _, session = api_client
    await _mark_prior_users_delivered(session)
    tid = _tid()
    user, _budget = await create_user_with_budget(session, telegram_id=tid, role="owner")
    await session.commit()
    await session.refresh(user)

    cutoff = user.created_at - timedelta(seconds=1)
    bot = AsyncMock()
    sent = await send_release_announcements(session, bot, cutoff, dry_run=False)
    assert sent == 0
    bot.send_message.assert_not_awaited()
    await session.refresh(user)
    assert user.release_announcement_delivered_at is None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_soft_deleted_user_skips_announcement(
    api_client: tuple[object, AsyncSession],
) -> None:
    _, session = api_client
    await _mark_prior_users_delivered(session)
    tid = _tid()
    user, _budget = await create_user_with_budget(session, telegram_id=tid, role="owner")
    user.is_deleted = True
    user.deleted_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(user)

    cutoff = datetime.now(timezone.utc) + timedelta(hours=1)
    bot = AsyncMock()
    sent = await send_release_announcements(session, bot, cutoff, dry_run=False)
    assert sent == 0
    bot.send_message.assert_not_awaited()
    await session.refresh(user)
    assert user.release_announcement_delivered_at is None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
async def test_dry_run_sends_nothing(
    api_client: tuple[object, AsyncSession],
) -> None:
    _, session = api_client
    await _mark_prior_users_delivered(session)
    tid = _tid()
    user, _budget = await create_user_with_budget(session, telegram_id=tid, role="owner")
    await session.commit()
    await session.refresh(user)

    cutoff = datetime.now(timezone.utc) + timedelta(hours=1)
    bot = AsyncMock()
    count = await send_release_announcements(session, bot, cutoff, dry_run=True)
    assert count == 1
    bot.send_message.assert_not_awaited()
    await session.refresh(user)
    assert user.release_announcement_delivered_at is None


def test_script_not_wired_into_bot_main() -> None:
    import bot.main as bot_main

    src = inspect.getsource(bot_main)
    assert "release_announcement" not in src
    assert "send_release_announcement" not in src
