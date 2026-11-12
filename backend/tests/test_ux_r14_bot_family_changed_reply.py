"""The bot answers a refused write (joined/left a family mid-write) instead of staying silent (ux-r14)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.family_guard import FamilyChangedError
from bot.main import reply_family_changed


def _update(lang: str, *, callback: bool = False):
    answer = AsyncMock()
    msg = SimpleNamespace(answer=answer)
    user = SimpleNamespace(language_code=lang)
    if callback:
        return SimpleNamespace(message=None, callback_query=SimpleNamespace(
            message=msg, from_user=user)), answer
    return SimpleNamespace(message=SimpleNamespace(answer=answer, from_user=user),
                           callback_query=None), answer


@pytest.mark.anyio
@pytest.mark.parametrize("lang,word", [("ru", "повтор"), ("uz", "qayta")])
async def test_user_gets_a_repeat_request_text(lang, word):
    upd, answer = _update(lang)
    assert await reply_family_changed(upd, FamilyChangedError()) is True
    answer.assert_awaited_once()
    assert word in answer.await_args.args[0].lower()


@pytest.mark.anyio
async def test_callback_update_is_answered_too():
    upd, answer = _update("ru", callback=True)
    assert await reply_family_changed(upd, FamilyChangedError()) is True
    answer.assert_awaited_once()


@pytest.mark.anyio
async def test_other_errors_are_not_swallowed():
    upd, answer = _update("ru")
    assert await reply_family_changed(upd, ValueError("x")) is False
    answer.assert_not_awaited()
