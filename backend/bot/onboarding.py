import secrets
import uuid
from typing import Literal

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import MINI_APP_URL
from app.db import async_session_factory
from app.models.family_budget import FamilyBudget
from app.models.user import User
from app.services.budget_seed import (
    SEED_EXPENSE_CATEGORIES,
    SEED_INCOME_CATEGORIES,
    SEED_WALLETS,
    assign_default_card_uzs,
    copy_seed_data,
    count_seed_rows,
)
from app.services.invite import (
    build_invite_link,
    cache_bot_username,
    get_cached_bot_username,
)
from app.services.member_texts import (
    invite_already_member,
    invite_family_full_chat,
    invite_link_invalid,
    join_confirm_prompt,
    join_has_other_members,
    join_personal_wallet_cap,
    welcome_invited,
)
from app.services.membership_lifecycle import (
    JoinBlockReason,
    count_active_members,
    count_all_wallets_for_user_budget,
    evaluate_join_from_own_budget,
)
from app.services.entity_limits import MEMBER_LIMIT

router = Router()

router = Router()

FlowType = Literal["owner", "member"]

MESSAGES: dict[str, dict[str, str]] = {
    "already_member": {
        "ru": "Вы уже состоите в Family Budget.",
        "uz": "Siz allaqachon Family Budget a'zosiz.",
    },
    "invalid_invite": {
        "ru": "Ссылка-приглашение недействительна или просрочена.",
        "uz": "Taklif havolasi yaroqsiz yoki muddati tugagan.",
    },
    "choose_language": {
        "ru": "Выберите язык:",
        "uz": "Tilni tanlang:",
    },
    "welcome_owner": {
        "ru": "Добро пожаловать! Вы создали Family Budget.",
        "uz": "Xush kelibsiz! Siz Family Budget yaratdingiz.",
    },
    "welcome_member": {
        "ru": "Добро пожаловать! Вы присоединились к Family Budget.",
        "uz": "Xush kelibsiz! Siz Family Budgetga qo'shildingiz.",
    },
    "invite_only_owner": {
        "ru": "Только Owner может приглашать участников.",
        "uz": "Faqat Owner a'zolarni taklif qila oladi.",
    },
    "not_registered": {
        "ru": "Сначала пройдите регистрацию через /start.",
        "uz": "Avval /start orqali ro'yxatdan o'ting.",
    },
}

SUPPORTED_LANGUAGES = frozenset({"ru", "uz"})

OPEN_APP_BUTTON: dict[str, str] = {
    "ru": "💰 Запустить приложение",
    "uz": "💰 Ilovani ochish",
}


class OnboardingStates(StatesGroup):
    choosing_language = State()


def t(key: str, language: str, **kwargs: str) -> str:
    lang = language if language in SUPPORTED_LANGUAGES else "ru"
    template = MESSAGES[key][lang]
    return template.format(**kwargs) if kwargs else template


def parse_start_payload(payload: str | None) -> tuple[FlowType, str | None]:
    if payload and payload.startswith("invite_"):
        token = payload.removeprefix("invite_")
        if token:
            return "member", token
    return "owner", None


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Русский", callback_data="lang:ru"),
                InlineKeyboardButton(text="O'zbekcha", callback_data="lang:uz"),
            ]
        ]
    )


def open_app_keyboard(language: str) -> ReplyKeyboardMarkup:
    lang = language if language in SUPPORTED_LANGUAGES else "ru"
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text=OPEN_APP_BUTTON[lang],
                    web_app=WebAppInfo(url=MINI_APP_URL),
                )
            ]
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def join_confirm_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Присоединиться",
                    callback_data=f"join_accept:{token}",
                )
            ],
            [InlineKeyboardButton(text="Отмена", callback_data="join_cancel")],
        ]
    )


async def resolve_bot_username(bot: Bot) -> str:
    bot_username = get_cached_bot_username()
    if bot_username is None:
        await cache_bot_username(bot)
        bot_username = get_cached_bot_username()
    if bot_username is None:
        raise RuntimeError("Telegram bot has no username")
    return bot_username


async def get_active_user_by_telegram_id(
    session: AsyncSession, telegram_id: int
) -> User | None:
    stmt = select(User).where(User.telegram_id == telegram_id, User.is_deleted.is_(False))
    return await session.scalar(stmt)


async def get_family_budget_by_invite_token(
    session: AsyncSession, token: str
) -> FamilyBudget | None:
    stmt = select(FamilyBudget).where(
        FamilyBudget.invite_token == token,
        FamilyBudget.is_deleted.is_(False),
    )
    return await session.scalar(stmt)


@router.message(CommandStart())
async def start_handler(
    message: Message, command: CommandObject, state: FSMContext
) -> None:
    if message.from_user is None:
        return

    telegram_id = message.from_user.id
    flow, invite_token = parse_start_payload(command.args)

    async with async_session_factory() as session:
        existing_user = await get_active_user_by_telegram_id(session, telegram_id)

        if existing_user is not None:
            if flow == "member" and invite_token:
                budget = await get_family_budget_by_invite_token(
                    session, invite_token
                )
                if budget is None:
                    await message.answer(invite_link_invalid())
                    return

                if existing_user.family_budget_id == budget.id:
                    await message.answer(invite_already_member(budget.name))
                    return

                if await count_active_members(session, budget.id) >= MEMBER_LIMIT:
                    await message.answer(invite_family_full_chat())
                    return

                block = await evaluate_join_from_own_budget(
                    session, existing_user, budget
                )
                if block == JoinBlockReason.HAS_OTHER_MEMBERS:
                    await message.answer(join_has_other_members())
                    return
                if block == JoinBlockReason.PERSONAL_WALLET_CAP:
                    wallet_count = await count_all_wallets_for_user_budget(
                        session, existing_user
                    )
                    await message.answer(join_personal_wallet_cap(wallet_count))
                    return

                await message.answer(
                    join_confirm_prompt(budget.name),
                    reply_markup=join_confirm_keyboard(invite_token),
                )
                return

            await message.answer(t("already_member", existing_user.language))
            return

        target_budget_id: uuid.UUID | None = None

        if flow == "member":
            assert invite_token is not None
            budget = await get_family_budget_by_invite_token(session, invite_token)
            if budget is None:
                await message.answer(invite_link_invalid())
                return
            if await count_active_members(session, budget.id) >= MEMBER_LIMIT:
                await message.answer(invite_family_full_chat())
                return
            target_budget_id = budget.id

    await state.set_state(OnboardingStates.choosing_language)
    await state.update_data(
        flow=flow,
        family_budget_id=str(target_budget_id) if target_budget_id else None,
        telegram_id=telegram_id,
        first_name=message.from_user.first_name,
        username=message.from_user.username,
    )
    await message.answer(t("choose_language", "ru"), reply_markup=language_keyboard())


@router.callback_query(F.data.startswith("lang:"), OnboardingStates.choosing_language)
async def language_callback(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if callback.from_user is None or callback.message is None:
        return

    language = callback.data.split(":", 1)[1] if callback.data else ""
    if language not in SUPPORTED_LANGUAGES:
        await callback.answer()
        return

    data = await state.get_data()
    flow: FlowType = data.get("flow", "owner")
    telegram_id = data.get("telegram_id", callback.from_user.id)
    existing_language: str | None = None
    invite_token: str | None = None
    member_budget_name = ""

    async with async_session_factory() as session:
        async with session.begin():
            existing_user = await get_active_user_by_telegram_id(session, telegram_id)
            if existing_user is not None:
                existing_language = existing_user.language
            elif flow == "owner":
                invite_token = secrets.token_urlsafe(16)
                budget = FamilyBudget(invite_token=invite_token)
                session.add(budget)
                await session.flush()

                user = User(
                    telegram_id=telegram_id,
                    family_budget_id=budget.id,
                    role="owner",
                    first_name=data.get("first_name"),
                    username=data.get("username"),
                    language=language,
                )
                session.add(user)
                await session.flush()
                await copy_seed_data(session, budget.id)
                await assign_default_card_uzs(session, user)
            else:
                budget_id = uuid.UUID(data["family_budget_id"])
                budget = await session.get(FamilyBudget, budget_id)
                if budget is None or budget.is_deleted:
                    existing_language = language
                    await callback.message.edit_text(invite_link_invalid())
                    await state.clear()
                    await callback.answer()
                    return
                if await count_active_members(session, budget_id) >= MEMBER_LIMIT:
                    existing_language = language
                    await callback.message.edit_text(invite_family_full_chat())
                    await state.clear()
                    await callback.answer()
                    return
                user = User(
                    telegram_id=telegram_id,
                    family_budget_id=budget_id,
                    role="member",
                    first_name=data.get("first_name"),
                    username=data.get("username"),
                    language=language,
                )
                session.add(user)
                await assign_default_card_uzs(session, user)
                member_budget_name = budget.name

    if existing_language is not None:
        await callback.message.edit_text(t("already_member", existing_language))
        await state.clear()
        await callback.answer()
        return

    if flow == "owner":
        welcome = t("welcome_owner", language)
    else:
        welcome = welcome_invited(member_budget_name)

    await callback.message.answer(welcome, reply_markup=open_app_keyboard(language))
    await callback.message.delete()
    await state.clear()
    await callback.answer()


@router.message(Command("invite"))
async def invite_handler(message: Message, bot: Bot) -> None:
    if message.from_user is None:
        return

    telegram_id = message.from_user.id
    language = "ru"
    error_key: str | None = None
    invite_token: str | None = None

    async with async_session_factory() as session:
        user = await get_active_user_by_telegram_id(session, telegram_id)
        if user is None:
            error_key = "not_registered"
        else:
            language = user.language
            if user.role != "owner":
                error_key = "invite_only_owner"
            else:
                budget = await session.get(FamilyBudget, user.family_budget_id)
                if budget is None or budget.is_deleted or not budget.invite_token:
                    error_key = "invalid_invite"
                else:
                    invite_token = budget.invite_token

    if error_key is not None:
        await message.answer(t(error_key, language))
        return

    assert invite_token is not None
    bot_username = await resolve_bot_username(bot)
    invite_link = build_invite_link(bot_username, invite_token)
    await message.answer(invite_link)
