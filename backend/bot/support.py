from __future__ import annotations

import uuid

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import SUPPORT_CHAT_ID
from app.db import async_session_factory
from app.models.family_budget import FamilyBudget
from app.models.support_message import SupportMessage
from app.models.user import User
from bot.onboarding import get_active_user_by_telegram_id

router = Router()

SUPPORTED_LANGUAGES = frozenset({"ru", "uz"})

STRINGS: dict[str, dict[str, str]] = {
    "entry": {
        "ru": "Написать в поддержку",
        "uz": "Qo'llab-quvvatlashga yozish",
    },
    "quick_1": {
        "ru": "Голосовое сообщение не распознаётся",
        "uz": "Ovozli xabar tanilmayapti",
    },
    "quick_2": {
        "ru": "Фото чека не распознаётся",
        "uz": "Chek fotosurati tanilmayapti",
    },
    "quick_3": {
        "ru": "Вопрос по категориям или кошелькам",
        "uz": "Kategoriyalar yoki hamyonlar bo'yicha savol",
    },
    "quick_4": {
        "ru": "Не приходят уведомления",
        "uz": "Bildirishnomalar kelmayapti",
    },
    "write_own": {
        "ru": "Свой вопрос",
        "uz": "Boshqa savol",
    },
    "free_text_prompt": {
        "ru": "Напишите ваш вопрос одним сообщением.",
        "uz": "Savolingizni bitta xabarda yozing.",
    },
    "confirmation": {
        "ru": "Сообщение отправлено. Мы ответим вам здесь же.",
        "uz": "Xabar yuborildi. Javobni shu yerda kutib turing.",
    },
}

QUICK_KEYS = ("quick_1", "quick_2", "quick_3", "quick_4")

ENTRY_LABELS = frozenset(STRINGS["entry"].values())

CALLBACK_QUICK_PREFIX = "support:quick:"
CALLBACK_OWN = "support:own"


class SupportStates(StatesGroup):
    awaiting_free_text = State()


def _lang(language: str) -> str:
    return language if language in SUPPORTED_LANGUAGES else "ru"


def support_entry_label(language: str) -> str:
    return STRINGS["entry"][_lang(language)]


def build_main_reply_keyboard(
    language: str = "ru",
) -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    rows: list[list[KeyboardButton]] = []
    if SUPPORT_CHAT_ID:
        rows.append([KeyboardButton(text=support_entry_label(language))])
    if not rows:
        # Telegram keeps the last reply keyboard shown in a chat until the
        # bot explicitly clears it — returning None here would leave a
        # stale keyboard from an earlier version in place forever.
        return ReplyKeyboardRemove()
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
    )


def support_options_keyboard(language: str) -> InlineKeyboardMarkup:
    lang = _lang(language)
    rows = [
        [InlineKeyboardButton(text=STRINGS[key][lang], callback_data=f"{CALLBACK_QUICK_PREFIX}{idx}")]
        for idx, key in enumerate(QUICK_KEYS)
    ]
    rows.append(
        [InlineKeyboardButton(text=STRINGS["write_own"][lang], callback_data=CALLBACK_OWN)]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_support_header(
    family_name: str,
    person_name: str,
    username: str | None,
) -> str:
    if username:
        return f"{family_name} — {person_name} (@{username})"
    return f"{family_name} — {person_name}"


async def relay_to_support(bot: Bot, *, header: str, text: str) -> int:
    msg = await bot.send_message(
        chat_id=int(SUPPORT_CHAT_ID),  # type: ignore[arg-type]
        text=f"{header}\n\n{text}",
    )
    return msg.message_id


async def _store_mapping(
    session: AsyncSession,
    *,
    forwarded_message_id: int,
    telegram_user_id: int,
    family_budget_id: uuid.UUID,
) -> None:
    session.add(
        SupportMessage(
            forwarded_message_id=forwarded_message_id,
            telegram_user_id=telegram_user_id,
            family_budget_id=family_budget_id,
        )
    )
    await session.commit()


async def _relay_user_message(
    bot: Bot,
    session: AsyncSession,
    user: User,
    budget: FamilyBudget,
    text: str,
    *,
    person_name: str | None,
    username: str | None,
) -> None:
    name = person_name or user.first_name or "User"
    header = build_support_header(budget.name, name, username or user.username)
    message_id = await relay_to_support(bot, header=header, text=text)
    await _store_mapping(
        session,
        forwarded_message_id=message_id,
        telegram_user_id=user.telegram_id,
        family_budget_id=user.family_budget_id,
    )


@router.message(F.text.in_(ENTRY_LABELS))
async def support_entry(message: Message, state: FSMContext) -> None:
    if not SUPPORT_CHAT_ID or message.from_user is None:
        return

    async with async_session_factory() as session:
        user = await get_active_user_by_telegram_id(session, message.from_user.id)
        if user is None:
            return
        language = user.language

    await state.clear()
    await message.answer(
        "\u200b",
        reply_markup=support_options_keyboard(language),
    )


@router.callback_query(F.data.startswith(CALLBACK_QUICK_PREFIX))
async def support_quick_option(callback: CallbackQuery, bot: Bot) -> None:
    if not SUPPORT_CHAT_ID or callback.from_user is None or callback.message is None:
        await callback.answer()
        return

    raw_idx = callback.data.removeprefix(CALLBACK_QUICK_PREFIX) if callback.data else ""
    try:
        idx = int(raw_idx)
    except ValueError:
        await callback.answer()
        return
    if idx < 0 or idx >= len(QUICK_KEYS):
        await callback.answer()
        return

    async with async_session_factory() as session:
        user = await get_active_user_by_telegram_id(session, callback.from_user.id)
        if user is None:
            await callback.answer()
            return
        budget = await session.get(FamilyBudget, user.family_budget_id)
        if budget is None or budget.is_deleted:
            await callback.answer()
            return
        language = user.language
        text = STRINGS[QUICK_KEYS[idx]][_lang(language)]
        await _relay_user_message(
            bot,
            session,
            user,
            budget,
            text,
            person_name=callback.from_user.first_name,
            username=callback.from_user.username,
        )

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(STRINGS["confirmation"][_lang(language)])
    await callback.answer()


@router.callback_query(F.data == CALLBACK_OWN)
async def support_own_question(callback: CallbackQuery, state: FSMContext) -> None:
    if not SUPPORT_CHAT_ID or callback.from_user is None or callback.message is None:
        await callback.answer()
        return

    async with async_session_factory() as session:
        user = await get_active_user_by_telegram_id(session, callback.from_user.id)
        if user is None:
            await callback.answer()
            return
        language = user.language

    await state.set_state(SupportStates.awaiting_free_text)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(STRINGS["free_text_prompt"][_lang(language)])
    await callback.answer()


@router.message(SupportStates.awaiting_free_text, F.text)
async def support_free_text(message: Message, state: FSMContext, bot: Bot) -> None:
    if not SUPPORT_CHAT_ID or message.from_user is None or not message.text:
        return

    async with async_session_factory() as session:
        user = await get_active_user_by_telegram_id(session, message.from_user.id)
        if user is None:
            await state.clear()
            return
        budget = await session.get(FamilyBudget, user.family_budget_id)
        if budget is None or budget.is_deleted:
            await state.clear()
            return
        language = user.language
        await _relay_user_message(
            bot,
            session,
            user,
            budget,
            message.text,
            person_name=message.from_user.first_name,
            username=message.from_user.username,
        )

    await state.clear()
    await message.answer(STRINGS["confirmation"][_lang(language)])


def _is_support_chat(message: Message) -> bool:
    if not SUPPORT_CHAT_ID:
        return False
    return message.chat.id == int(SUPPORT_CHAT_ID)


@router.message(F.func(_is_support_chat), F.reply_to_message)
async def support_inbound_reply(message: Message, bot: Bot) -> None:
    if not _is_support_chat(message):
        return
    if not message.reply_to_message or not message.text:
        return

    forwarded_id = message.reply_to_message.message_id
    async with async_session_factory() as session:
        mapping = await session.scalar(
            select(SupportMessage).where(
                SupportMessage.forwarded_message_id == forwarded_id
            )
        )
        if mapping is None:
            return
        await bot.send_message(mapping.telegram_user_id, message.text)
