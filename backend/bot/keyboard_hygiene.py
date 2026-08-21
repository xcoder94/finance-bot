"""One-time cleanup for the reply keyboard removed in commit 96f5318.

That commit took the app-launcher `KeyboardButton` off the persistent reply
keyboard (Telegram never delivers initData to Mini Apps launched from a
keyboard button — that launch path is impossible). Telegram keeps the last
reply keyboard it sent in a chat until a later message explicitly overrides
or removes it — sending `reply_markup=None` does NOT clear it. Every handler
in this codebase that has nothing to show simply omits `reply_markup` (which
the aiogram method models default to `None`), and `build_main_reply_keyboard`
has no production call site any more, so without this middleware the old
launcher button stays tappable forever for anyone who already had it on
screen — a dead control, and one that would never be reached by fixing any
single handler, since dormant users may never trigger one again.

This request middleware defaults an unset `reply_markup` to
`ReplyKeyboardRemove()` on outgoing `Send*` Bot API calls, so the next
message any user receives clears whatever reply keyboard Telegram still has
on screen for them. It never touches calls that already specify a
`reply_markup` (inline keyboards, explicit reply keyboards, or explicit
removal), and it deliberately excludes `Edit*` methods, whose `reply_markup`
field only accepts `InlineKeyboardMarkup` — passing a `ReplyKeyboardRemove`
there would be rejected by Telegram.

This is a cleanup for a keyboard that no longer exists, not a permanent
policy against reply keyboards: it self-disables the moment a legitimate one
can exist. `SUPPORT_CHAT_ID` is what turns `build_main_reply_keyboard` from
"nothing to show" into the real support-entry reply keyboard; once the PM
sets it in production, this middleware must stop touching `reply_markup`
altogether, or it would strip that keyboard off the user's screen the moment
any markup-less message went out. `SUPPORT_CHAT_ID` is read from `app.config`
at call time (not imported at module load) so it reflects the current
configuration — including a value a test sets after import.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import app.config
from aiogram.client.session.middlewares.base import (
    BaseRequestMiddleware,
    NextRequestMiddlewareType,
)
from aiogram.types import ReplyKeyboardRemove

if TYPE_CHECKING:
    from aiogram.client.bot import Bot
    from aiogram.methods import Response, TelegramMethod
    from aiogram.methods.base import TelegramType


class ClearStaleReplyKeyboardMiddleware(BaseRequestMiddleware):
    async def __call__(
        self,
        make_request: NextRequestMiddlewareType[TelegramType],
        bot: Bot,
        method: TelegramMethod[TelegramType],
    ) -> Response[TelegramType]:
        if app.config.SUPPORT_CHAT_ID:
            # A legitimate reply keyboard (the support entry) can now exist.
            # Leave every reply_markup exactly as the handler set it.
            return await make_request(bot, method)

        model_fields = getattr(type(method), "model_fields", {})
        if (
            type(method).__name__.startswith("Send")
            and "reply_markup" in model_fields
            and method.reply_markup is None
        ):
            method.reply_markup = ReplyKeyboardRemove()
        return await make_request(bot, method)
