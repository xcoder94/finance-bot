"""Stale reply keyboard must be cleared, not left in place.

Telegram keeps the last reply keyboard shown in a chat until a later
message explicitly overrides or removes it — `reply_markup=None` does NOT
clear it. `bot.support.build_main_reply_keyboard()` / `bot.onboarding.
open_app_keyboard()` used to return `None` when there was nothing to show
(e.g. SUPPORT_CHAT_ID unset in production), which left the removed
app-launcher reply-keyboard button tappable forever — a dead control.
`ClearStaleReplyKeyboardMiddleware` is the single place that guarantees the
next Bot API `Send*` call with no explicit `reply_markup` clears whatever
reply keyboard Telegram still has on screen, covering every message path —
including users who never trigger a keyboard-building handler again.
"""

from __future__ import annotations

import asyncio

from aiogram.methods import EditMessageReplyMarkup, SendMessage, SendPhoto
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from bot.keyboard_hygiene import ClearStaleReplyKeyboardMiddleware
from bot.onboarding import open_app_keyboard
from bot.support import build_main_reply_keyboard


async def _next(bot, method):
    return method


def test_build_main_reply_keyboard_removes_instead_of_none(monkeypatch) -> None:
    monkeypatch.setattr("bot.support.SUPPORT_CHAT_ID", None)
    assert isinstance(build_main_reply_keyboard("ru"), ReplyKeyboardRemove)


def test_open_app_keyboard_removes_instead_of_none(monkeypatch) -> None:
    monkeypatch.setattr("bot.support.SUPPORT_CHAT_ID", None)
    assert isinstance(open_app_keyboard("ru"), ReplyKeyboardRemove)


def test_build_main_reply_keyboard_unchanged_when_support_configured(
    monkeypatch,
) -> None:
    monkeypatch.setattr("bot.support.SUPPORT_CHAT_ID", "-100123")
    kb = build_main_reply_keyboard("ru")
    assert isinstance(kb, ReplyKeyboardMarkup)
    assert isinstance(kb.keyboard[0][0], KeyboardButton)


def test_middleware_defaults_missing_reply_markup_to_remove(monkeypatch) -> None:
    monkeypatch.setattr("app.config.SUPPORT_CHAT_ID", None)

    async def _run() -> None:
        mw = ClearStaleReplyKeyboardMiddleware()
        method = SendMessage(chat_id=1, text="hello")
        await mw(_next, bot=None, method=method)
        assert isinstance(method.reply_markup, ReplyKeyboardRemove)

    asyncio.run(_run())


def test_middleware_self_disables_once_support_keyboard_configured(
    monkeypatch,
) -> None:
    """Once SUPPORT_CHAT_ID is set, a legitimate reply keyboard can exist —
    the middleware must not strip a markup-less message's reply_markup."""
    monkeypatch.setattr("app.config.SUPPORT_CHAT_ID", "-100123")

    async def _run() -> None:
        mw = ClearStaleReplyKeyboardMiddleware()
        method = SendMessage(chat_id=1, text="hello")
        await mw(_next, bot=None, method=method)
        assert method.reply_markup is None

    asyncio.run(_run())


def test_middleware_leaves_explicit_reply_markup_untouched(monkeypatch) -> None:
    monkeypatch.setattr("app.config.SUPPORT_CHAT_ID", None)

    async def _run() -> None:
        mw = ClearStaleReplyKeyboardMiddleware()
        inline = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="x", callback_data="x")]]
        )
        method = SendMessage(chat_id=1, text="hello", reply_markup=inline)
        await mw(_next, bot=None, method=method)
        assert method.reply_markup is inline

    asyncio.run(_run())


def test_middleware_leaves_edit_methods_untouched(monkeypatch) -> None:
    monkeypatch.setattr("app.config.SUPPORT_CHAT_ID", None)

    async def _run() -> None:
        mw = ClearStaleReplyKeyboardMiddleware()
        method = EditMessageReplyMarkup(chat_id=1, message_id=1, reply_markup=None)
        await mw(_next, bot=None, method=method)
        assert method.reply_markup is None

    asyncio.run(_run())


def test_middleware_applies_to_other_send_methods_too(monkeypatch) -> None:
    monkeypatch.setattr("app.config.SUPPORT_CHAT_ID", None)

    async def _run() -> None:
        mw = ClearStaleReplyKeyboardMiddleware()
        method = SendPhoto(chat_id=1, photo="file_id")
        await mw(_next, bot=None, method=method)
        assert isinstance(method.reply_markup, ReplyKeyboardRemove)

    asyncio.run(_run())
