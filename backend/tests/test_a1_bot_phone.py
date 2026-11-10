"""a-1 backend-b: phone request right after a new user's first /start.

Real aiogram Dispatcher/Update/Bot objects and a real Postgres; only the Telegram network
call (FakeBot) and the AI parser (override at its outer boundary) are replaced.
"""

from __future__ import annotations

import logging
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram import Dispatcher
from aiogram.methods import SendMessage
from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove
from sqlalchemy import func, select

from app.models.transaction import Transaction
from app.models.user import User
from app.parsing.stub import StubParser
from app.parsing.types import ParseResponse, ParsedOperation
from bot import phone_prompt
from bot.keyboard_hygiene import ClearStaleReplyKeyboardMiddleware
from bot.onboarding import language_callback
from bot.onboarding import router as onboarding_router
from bot.phone_prompt import router as phone_router
from bot.quick_entry.handlers import router as quick_entry_router
from bot.quick_entry.handlers import set_parser_override
from tests.test_m3_4_bot_shopping import FakeBot, _update
from tests.test_quick_entry_flow import (
    SessionFactory,
    create_user,
    pytestmark,  # noqa: F401
    rollback_session,
    seed_taxi_setup,
)

RU_PROMPT = (
    "Если хотите, поделитесь номером телефона — так нам проще связаться с вами, "
    "если что-то пойдёт не так. Можно пропустить."
)
UZ_PROMPT = (
    "Xohlasangiz, telefon raqamingizni yuboring — biror muammo bo'lsa, "
    "siz bilan bog'lanish osonroq bo'ladi. O'tkazib yuborish mumkin."
)


@pytest.fixture(autouse=True)
def _reset():
    set_parser_override(None)
    phone_prompt.pending_keyboard_restore.clear()
    yield
    set_parser_override(None)
    phone_prompt.pending_keyboard_restore.clear()


def _patch_sessions(monkeypatch, session) -> None:
    factory = SessionFactory(session)
    for target in (
        "bot.phone_prompt.async_session_factory",
        "bot.onboarding.async_session_factory",
        "bot.quick_entry.handlers.async_session_factory",
    ):
        monkeypatch.setattr(target, factory)


async def _feed(bot, update) -> None:
    dp = Dispatcher()
    dp.include_router(phone_router)
    dp.include_router(onboarding_router)
    dp.include_router(quick_entry_router)
    try:
        await dp.feed_update(bot, update)
    finally:
        for r in (phone_router, onboarding_router, quick_entry_router):
            r._parent_router = None


def _buttons(markup) -> list[tuple[str, bool]]:
    return [(b.text, bool(b.request_contact)) for row in markup.keyboard for b in row]


async def _fresh(session, user) -> User:
    await session.refresh(user)
    return user


async def _prompted_user(session, *, language="ru", tid=9_510_001):
    user, budget = await create_user(session, telegram_id=tid)
    user.language = language
    user.phone_prompted_at = phone_prompt._now()
    await session.flush()
    return user, budget


def _contact(tid: int, owner_id: int | None, number="998901234567") -> dict:
    return {"contact": {"phone_number": number, "first_name": "T", "user_id": owner_id}}


async def _new_user_callback(session, monkeypatch, *, language: str, flow="owner", budget_id=None):
    """The real language_callback for a brand-new user (savepoint session, begin() stubbed)."""
    _patch_sessions(monkeypatch, session)
    session.begin = lambda: _Tx()
    tid = 9_520_000 + uuid.uuid4().int % 100_000
    message = SimpleNamespace(answer=AsyncMock(), delete=AsyncMock(), edit_text=AsyncMock())
    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=tid), message=message, data=f"lang:{language}", answer=AsyncMock()
    )
    data = {"flow": flow, "telegram_id": tid, "first_name": "T", "username": None,
            "family_budget_id": str(budget_id) if budget_id else None}
    state = SimpleNamespace(get_data=AsyncMock(return_value=data), clear=AsyncMock())
    await language_callback(callback, state, SimpleNamespace())
    user = await session.scalar(select(User).where(User.telegram_id == tid))
    return user, message


class _Tx:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_a) -> None:
        return None


class TestNewUserPrompt:
    """PRD-ux U7: no phone request right after the welcome (it comes after the 3rd operation,
    see tests/test_ux_p6_phone.py). The prompt itself is unchanged."""

    @pytest.mark.parametrize("language,text,share,skip", [
        ("ru", RU_PROMPT, "Поделиться номером", "Пропустить"),
        ("uz", UZ_PROMPT, "Raqamni yuborish", "O'tkazib yuborish"),
    ])
    async def test_prompt_text_and_two_buttons(self, language, text, share, skip) -> None:
        assert phone_prompt.prompt_text(language) == text
        markup = phone_prompt.prompt_keyboard(language)
        assert isinstance(markup, ReplyKeyboardMarkup)
        assert _buttons(markup) == [(share, True), (skip, False)]

    async def test_owner_welcome_has_no_prompt(self, monkeypatch) -> None:
        from app.services.member_texts import welcome_solo

        async with rollback_session() as session:
            monkeypatch.setattr("bot.onboarding.assign_default_card_uzs", AsyncMock())
            user, message = await _new_user_callback(session, monkeypatch, language="ru")
            assert [c.args[0] for c in message.answer.await_args_list] == [welcome_solo("ru")]
            assert user.phone_prompted_at is None and user.phone is None

    async def test_existing_user_start_gets_no_prompt(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, _ = await create_user(session, telegram_id=9_510_060)
            _patch_sessions(monkeypatch, session)
            bot = FakeBot()
            await _feed(bot, _update(user.telegram_id, text="/start",
                                     entities=[{"type": "bot_command", "offset": 0, "length": 6}]))
            assert [m.text for m in bot.sent] == ["Вы уже в семейном бюджете «Семейный бюджет»."]
            assert (await _fresh(session, user)).phone_prompted_at is None


class TestContact:
    @pytest.mark.parametrize("language,saved", [("ru", "Спасибо, номер сохранён."), ("uz", "Rahmat, raqam saqlandi.")])
    async def test_own_contact_saved_with_plus_and_keyboard_normal(self, monkeypatch, language, saved) -> None:
        async with rollback_session() as session:
            user, _ = await _prompted_user(session, language=language)
            _patch_sessions(monkeypatch, session)
            bot = FakeBot()
            await _feed(bot, _update(user.telegram_id, **_contact(user.telegram_id, user.telegram_id)))
            u = await _fresh(session, user)
            assert u.phone == "+998901234567"
            assert u.phone_shared_at is not None and u.phone_prompt_closed_at is not None
            assert [m.text for m in bot.sent] == [saved]
            # ordinary keyboard: the launcher keyboard is removed (no support chat configured)
            assert isinstance(bot.sent[0].reply_markup, ReplyKeyboardRemove)

    async def test_own_contact_with_plus_and_spaces_normalised(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, _ = await _prompted_user(session)
            _patch_sessions(monkeypatch, session)
            await _feed(FakeBot(), _update(user.telegram_id,
                                           **_contact(1, user.telegram_id, "+998 90 123-45-67")))
            assert (await _fresh(session, user)).phone == "+998901234567"

    @pytest.mark.parametrize("language,text", [("ru", "Нужен ваш номер — кнопка ниже."),
                                               ("uz", "Sizning raqamingiz kerak — pastdagi tugma.")])
    @pytest.mark.parametrize("owner_id", [777, None])
    async def test_foreign_contact_not_saved_keyboard_stays(self, monkeypatch, language, text, owner_id) -> None:
        async with rollback_session() as session:
            user, _ = await _prompted_user(session, language=language)
            _patch_sessions(monkeypatch, session)
            bot = FakeBot()
            await _feed(bot, _update(user.telegram_id, **_contact(1, owner_id)))
            u = await _fresh(session, user)
            assert u.phone is None and u.phone_shared_at is None and u.phone_prompt_closed_at is None
            assert [m.text for m in bot.sent] == [text]
            assert isinstance(bot.sent[0].reply_markup, ReplyKeyboardMarkup)
            assert len(_buttons(bot.sent[0].reply_markup)) == 2
            # the prompt is still open: the own contact afterwards is accepted
            await _feed(bot, _update(user.telegram_id, **_contact(1, user.telegram_id)))
            assert (await _fresh(session, user)).phone == "+998901234567"

    async def test_own_contact_without_open_prompt_is_saved_and_confirmed(self, monkeypatch) -> None:
        """fix1 B6: an old user / closed prompt: the number is still accepted."""
        async with rollback_session() as session:
            user, _ = await create_user(session, telegram_id=9_510_070)  # existing user
            _patch_sessions(monkeypatch, session)
            bot = FakeBot()
            await _feed(bot, _update(user.telegram_id, **_contact(1, user.telegram_id)))
            u = await _fresh(session, user)
            assert u.phone == "+998901234567" and u.phone_shared_at is not None
            assert [m.text for m in bot.sent] == ["Спасибо, номер сохранён."]
            assert isinstance(bot.sent[0].reply_markup, ReplyKeyboardRemove)

    async def test_foreign_contact_without_open_prompt_asks_for_own(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, _ = await create_user(session, telegram_id=9_510_071)
            _patch_sessions(monkeypatch, session)
            bot = FakeBot()
            await _feed(bot, _update(user.telegram_id, **_contact(1, 777)))
            assert (await _fresh(session, user)).phone is None
            assert [m.text for m in bot.sent] == ["Нужен ваш номер — кнопка ниже."]

    async def test_contact_from_unknown_user_is_ignored(self, monkeypatch) -> None:
        async with rollback_session() as session:
            _patch_sessions(monkeypatch, session)
            bot = FakeBot()
            await _feed(bot, _update(9_510_072, **_contact(1, 9_510_072)))
            assert bot.sent == []

    async def test_second_contact_after_close_saves_latest(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, _ = await _prompted_user(session)
            _patch_sessions(monkeypatch, session)
            bot = FakeBot()
            await _feed(bot, _update(user.telegram_id, **_contact(1, user.telegram_id)))
            closed = (await _fresh(session, user)).phone_prompt_closed_at
            await _feed(bot, _update(user.telegram_id, **_contact(1, user.telegram_id, "998991112233")))
            u = await _fresh(session, user)
            assert u.phone == "+998991112233" and u.phone_prompt_closed_at == closed

    async def test_phone_never_in_logs(self, monkeypatch, caplog) -> None:
        async with rollback_session() as session:
            user, _ = await _prompted_user(session)
            _patch_sessions(monkeypatch, session)
            with caplog.at_level(logging.DEBUG):
                await _feed(FakeBot(), _update(user.telegram_id, **_contact(1, user.telegram_id)))
            assert "998901234567" not in caplog.text


class TestSkipAndOtherMessage:
    @pytest.mark.parametrize("language,label,reply", [
        ("ru", "Пропустить", "Хорошо. Записывайте траты сообщением."),
        ("uz", "O'tkazib yuborish", "Mayli. Xarajatlarni xabar bilan yozing."),
    ])
    async def test_skip(self, monkeypatch, language, label, reply) -> None:
        async with rollback_session() as session:
            user, _ = await _prompted_user(session, language=language)
            _patch_sessions(monkeypatch, session)
            bot = FakeBot()
            await _feed(bot, _update(user.telegram_id, text=label))
            u = await _fresh(session, user)
            assert u.phone is None and u.phone_prompt_closed_at is not None
            assert [m.text for m in bot.sent] == [reply]
            assert isinstance(bot.sent[0].reply_markup, ReplyKeyboardRemove)

    async def test_skip_without_open_prompt_is_a_short_reply_not_a_parse_error(self, monkeypatch) -> None:
        """fix1 B2/B6: "Skip" tapped on a leftover keyboard."""
        async with rollback_session() as session:
            user, _ = await create_user(session, telegram_id=9_510_080)
            _patch_sessions(monkeypatch, session)
            bot = FakeBot()
            await _feed(bot, _update(user.telegram_id, text="Пропустить"))
            assert [m.text for m in bot.sent] == ["Хорошо. Записывайте траты сообщением."]
            assert isinstance(bot.sent[0].reply_markup, ReplyKeyboardRemove)
            assert (await _fresh(session, user)).phone_prompt_closed_at is None

    async def test_expense_text_instead_of_answer_is_created_and_prompt_closed(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget = await _prompted_user(session)
            wallet, taxi = await seed_taxi_setup(session, user, budget)
            _patch_sessions(monkeypatch, session)
            set_parser_override(StubParser(responses={"такси 25000": ParseResponse(operations=[
                ParsedOperation(type="expense", amount=25000, currency="UZS", wallet_hint=None, category="Такси", comment=None)])}))
            bot = FakeBot()
            await _feed(bot, _update(user.telegram_id, text="такси 25000"))
            u = await _fresh(session, user)
            assert u.phone is None and u.phone_prompt_closed_at is not None
            n = await session.scalar(select(func.count()).select_from(Transaction)
                                     .where(Transaction.family_budget_id == budget.id))
            assert n == 1
            # the card keeps its inline buttons; the prompt keyboard is removed right away by a
            # separate short message carrying the ordinary keyboard (fix1 B2)
            assert phone_prompt.pending_keyboard_restore == {}
            assert len(bot.sent) == 2
            assert isinstance(bot.sent[0].reply_markup, ReplyKeyboardRemove)
            assert bot.sent[0].text == "Хорошо."
            card = bot.sent[1]  # the spend card is intact, with its inline buttons
            assert "25 000" in card.text and not isinstance(card.reply_markup, (ReplyKeyboardMarkup, ReplyKeyboardRemove))
            n_sent = len(bot.sent)
            # and the prompt never comes back
            await _feed(bot, _update(user.telegram_id, text="Пропустить"))
            assert (await _fresh(session, user)).phone_prompt_closed_at == u.phone_prompt_closed_at
            # B2: "Skip" after closing is answered shortly, never with "amount not found"
            assert len(bot.sent) == n_sent + 1
            assert bot.sent[-1].text == "Хорошо. Записывайте траты сообщением."
            assert isinstance(bot.sent[-1].reply_markup, ReplyKeyboardRemove)

    async def test_repeat_start_does_not_prompt_again(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, _ = await _prompted_user(session)
            user.phone_prompt_closed_at = phone_prompt._now()
            await session.flush()
            _patch_sessions(monkeypatch, session)
            bot = FakeBot()
            await _feed(bot, _update(user.telegram_id, text="/start",
                                     entities=[{"type": "bot_command", "offset": 0, "length": 6}]))
            assert [m.text for m in bot.sent] == ["Вы уже в семейном бюджете «Семейный бюджет»."]
            assert phone_prompt.pending_keyboard_restore == {}


class TestKeyboardRestoreMiddleware:
    async def test_next_send_gets_ordinary_keyboard_once(self, monkeypatch) -> None:
        sent: list[SendMessage] = []

        async def make_request(bot, method):
            sent.append(method)

        phone_prompt.pending_keyboard_restore[42] = "ru"
        mw = ClearStaleReplyKeyboardMiddleware()
        # SUPPORT_CHAT_ID set: the middleware would normally leave reply_markup alone
        monkeypatch.setattr("app.config.SUPPORT_CHAT_ID", -100123)
        monkeypatch.setattr("bot.support.SUPPORT_CHAT_ID", -100123)
        await mw(make_request, None, SendMessage(chat_id=42, text="x"))
        await mw(make_request, None, SendMessage(chat_id=42, text="y"))
        assert isinstance(sent[0].reply_markup, ReplyKeyboardMarkup)  # support keyboard = ordinary
        assert sent[1].reply_markup is None
        assert 42 not in phone_prompt.pending_keyboard_restore

    async def test_explicit_markup_is_kept_and_other_chats_untouched(self) -> None:
        sent: list[SendMessage] = []

        async def make_request(bot, method):
            sent.append(method)

        phone_prompt.pending_keyboard_restore[42] = "ru"
        marker = ReplyKeyboardRemove()
        mw = ClearStaleReplyKeyboardMiddleware()
        await mw(make_request, None, SendMessage(chat_id=42, text="x", reply_markup=marker))
        await mw(make_request, None, SendMessage(chat_id=43, text="y"))
        assert sent[0].reply_markup is marker
        assert 42 in phone_prompt.pending_keyboard_restore
