"""ux-p5 backend-a: one bot text catalogue, RU/UZ, language-aware /start and membership texts."""

from __future__ import annotations

import re
import string
import uuid
from unittest.mock import AsyncMock

import pytest
from aiogram.types import ReplyKeyboardMarkup

from app.services import member_texts
from app.services.bot_texts import CATALOGUE, resolve_language, t
from bot import phone_prompt
from bot.onboarding import (
    OPEN_APP_BUTTON_LABEL,
    greeting_inline_keyboard,
    join_confirm_keyboard,
)
from tests.test_a1_bot_phone import (
    _feed,
    _new_user_callback,
    _patch_sessions,
    _update,
    FakeBot,
    create_user,
    rollback_session,
)
from tests.test_quick_entry_flow import pytestmark  # noqa: F401

# PRD.md §18.1 / §18.2 verbatim
RU_SOLO = (
    "Chontak — семейный бюджет.\n\nЗаписывайте траты прямо здесь, сообщением:\n"
    "`такси 25 тысяч`\n\nКошельки, категории и аналитика — в приложении."
)
RU_INVITED = (
    "Вы присоединились к бюджету «Семья Юсуповых».\n"
    "Всё, что вы запишете, увидят остальные участники.\n\n"
    "Записывайте траты прямо здесь, сообщением:\n`такси 25 тысяч`\n\n"
    "Кошельки, цели и аналитика — в приложении."
)
BAD_APOSTROPHES = "ʻʼ’‘´"
CYRILLIC = re.compile(r"[А-Яа-яЁё]")


def _fields(template: str) -> set[str]:
    return {f for _, f, _, _ in string.Formatter().parse(template) if f}


@pytest.mark.parametrize("key", sorted(CATALOGUE))
def test_every_key_has_ru_and_uz(key: str) -> None:
    entry = CATALOGUE[key]
    assert set(entry) == {"ru", "uz"}
    assert entry["ru"].strip() and entry["uz"].strip()
    assert CYRILLIC.search(entry["ru"])
    assert not CYRILLIC.search(entry["uz"]), "UZ must be Latin"
    assert not any(ch in entry["uz"] for ch in BAD_APOSTROPHES)
    assert _fields(entry["ru"]) == _fields(entry["uz"])
    for lang in ("ru", "uz"):
        assert "Family Budget" not in entry[lang]
        assert "Owner" not in entry[lang]


def test_catalogue_is_not_empty_and_has_moved_groups() -> None:
    groups = {k.split(".")[0] for k in CATALOGUE}
    assert {"welcome", "button", "phone", "member", "onboarding"} <= groups


def test_t_picks_language_and_falls_back_to_ru_only_when_unknown() -> None:
    class U:
        language = "uz"

    assert t(U(), "button.open_app") == "Ilovani ochish"
    assert t("uz", "button.open_app") == "Ilovani ochish"
    assert t("ru", "button.open_app") == "Открыть приложение"
    for unknown in (None, "", "en", "xx"):
        assert resolve_language(unknown) == "ru"
        assert t(unknown, "button.open_app") == "Открыть приложение"
    assert t("uz", "member.already_member", budget_name="Oila") == (
        "Siz allaqachon «Oila» byudjeti a'zosisiz."
    )


def test_ru_welcome_texts_verbatim_prd_18() -> None:
    assert t("ru", "welcome.solo") == RU_SOLO
    assert t("ru", "welcome.invited", budget_name="Семья Юсуповых") == RU_INVITED
    assert member_texts.welcome_solo() == RU_SOLO
    assert member_texts.welcome_invited("Семья Юсуповых") == RU_INVITED


def test_uz_welcome_texts_are_uzbek() -> None:
    solo = member_texts.welcome_solo("uz")
    assert solo.startswith("Chontak — oilaviy byudjet.")
    assert "`taksi 25 ming`" in solo
    assert not CYRILLIC.search(solo)
    invited = member_texts.welcome_invited("Oila", "uz")
    assert "«Oila»" in invited and not CYRILLIC.search(invited)


def test_stale_strings_fixed() -> None:
    assert t("ru", "onboarding.already_member") == "Вы уже состоите в Chontak."
    assert t("ru", "onboarding.invite_only_owner") == (
        "Только владелец может приглашать участников."
    )


def test_member_texts_wrappers_keep_ru_default_and_accept_language() -> None:
    assert member_texts.invite_already_member("Х") == "Вы уже участник бюджета «Х»."
    assert member_texts.invite_already_member("Х", "uz") == t(
        "uz", "member.already_member", budget_name="Х"
    )
    assert member_texts.join_personal_wallet_cap(7, "uz") == t(
        "uz", "member.join_personal_wallet_cap", count=7
    )
    assert member_texts.departed_label("Али") == "Али (бывший участник)"
    assert member_texts.transfer_accepted_to_former("А", "Б", "uz") == t(
        "uz", "member.transfer_accepted_to_former", name="А", budget_name="Б"
    )


def test_keyboards_follow_language() -> None:
    import bot.onboarding as ob

    ob.MINI_APP_URL = "https://example.test/app"
    ru = greeting_inline_keyboard().inline_keyboard[0][0]
    uz = greeting_inline_keyboard("uz").inline_keyboard[0][0]
    assert ru.text == OPEN_APP_BUTTON_LABEL == "Открыть приложение"
    assert uz.text == "Ilovani ochish"
    rows = join_confirm_keyboard("tok", "uz").inline_keyboard
    assert [r[0].text for r in rows] == ["Qo'shilish", "Bekor qilish"]
    rows_ru = join_confirm_keyboard("tok").inline_keyboard
    assert [r[0].text for r in rows_ru] == ["Присоединиться", "Отмена"]
    assert rows[0][0].callback_data == "join_accept:tok" == rows_ru[0][0].callback_data
    assert rows[1][0].callback_data == "join_cancel"


def test_transfer_offer_keyboard_follows_language() -> None:
    from app.services.ownership_transfer import transfer_offer_keyboard

    tid = uuid.uuid4()
    uz = transfer_offer_keyboard(tid, "uz").inline_keyboard[0]
    ru = transfer_offer_keyboard(tid).inline_keyboard[0]
    assert [b.text for b in uz] == ["Qabul qilish", "Rad etish"]
    assert [b.text for b in ru] == ["Принять", "Отказаться"]
    assert uz[0].callback_data == ru[0].callback_data


def test_phone_prompt_strings_come_from_catalogue() -> None:
    for lang in ("ru", "uz"):
        assert phone_prompt.prompt_text(lang) == CATALOGUE["phone.prompt"][lang]
    kb = phone_prompt.prompt_keyboard("uz")
    assert [b.text for row in kb.keyboard for b in row] == [
        "Raqamni yuborish",
        "O'tkazib yuborish",
    ]
    assert phone_prompt.STRINGS["skip"]["uz"] == "O'tkazib yuborish"


async def test_acceptance_1_fresh_uz_account_start_is_uzbek(monkeypatch) -> None:
    import bot.onboarding as ob

    ob.MINI_APP_URL = "https://example.test/app"
    async with rollback_session() as session:
        monkeypatch.setattr("bot.onboarding.assign_default_card_uzs", AsyncMock())
        user, message = await _new_user_callback(session, monkeypatch, language="uz")
        calls = message.answer.await_args_list
        assert calls[0].args[0] == member_texts.welcome_solo("uz")
        assert calls[0].kwargs["reply_markup"].inline_keyboard[0][0].text == "Ilovani ochish"
        assert calls[1].args[0] == CATALOGUE["phone.prompt"]["uz"]
        assert isinstance(calls[1].kwargs["reply_markup"], ReplyKeyboardMarkup)


async def test_invited_uz_member_welcome_is_uzbek(monkeypatch) -> None:
    async with rollback_session() as session:
        _owner, budget = await create_user(session, telegram_id=9_530_001)
        monkeypatch.setattr("bot.onboarding.assign_default_card_uzs", AsyncMock())
        _user, message = await _new_user_callback(
            session, monkeypatch, language="uz", flow="member", budget_id=budget.id
        )
        first = message.answer.await_args_list[0].args[0]
        assert first == member_texts.welcome_invited(budget.name, "uz")


async def test_existing_uz_user_start_reply_is_uzbek(monkeypatch) -> None:
    async with rollback_session() as session:
        user, _ = await create_user(session, telegram_id=9_530_010)
        user.language = "uz"
        await session.flush()
        _patch_sessions(monkeypatch, session)
        bot = FakeBot()
        await _feed(
            bot,
            _update(user.telegram_id, text="/start",
                    entities=[{"type": "bot_command", "offset": 0, "length": 6}]),
        )
        assert [m.text for m in bot.sent] == ["Siz allaqachon «Семейный бюджет» oilaviy byudjetidasiz."]


async def test_existing_ru_user_start_reply_is_ru_with_chontak(monkeypatch) -> None:
    async with rollback_session() as session:
        user, _ = await create_user(session, telegram_id=9_530_011)
        _patch_sessions(monkeypatch, session)
        bot = FakeBot()
        await _feed(
            bot,
            _update(user.telegram_id, text="/start",
                    entities=[{"type": "bot_command", "offset": 0, "length": 6}]),
        )
        assert [m.text for m in bot.sent] == ["Вы уже в семейном бюджете «Семейный бюджет»."]
