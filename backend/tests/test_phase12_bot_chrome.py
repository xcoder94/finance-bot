"""Phase 12 — bot chrome outside quick entry."""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiogram.filters import Command
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from app.services.member_texts import welcome_invited, welcome_solo
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
    monkeypatch.setattr("bot.onboarding.MINI_APP_URL", "https://example.test/app")
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
    monkeypatch.setattr("bot.onboarding.MINI_APP_URL", None)
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
