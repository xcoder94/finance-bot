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
    Message,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_factory
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.income_category import IncomeCategory
from app.models.user import User
from app.models.wallet import Wallet
from app.services.invite import (
    build_invite_link,
    cache_bot_username,
    get_cached_bot_username,
)

router = Router()

FlowType = Literal["owner", "member"]

SEED_INCOME_CATEGORIES: list[tuple[str, str]] = [
    ("Зарплата", "salary"),
    ("Подработка", "side_job"),
    ("Подарки", "gifts"),
    ("Прочее", "income_other"),
]

SEED_EXPENSE_CATEGORIES: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "Еда": (
        "food",
        [
            ("Продукты", "groceries"),
            ("Обед", "lunch"),
            ("Вода и напитки", "drinks_water"),
            ("Кафе", "cafe"),
        ],
    ),
    "Развлечения": (
        "entertainment",
        [
            ("Playstation", "playstation"),
            ("Кино", "cinema"),
            ("Подписки", "subscriptions"),
        ],
    ),
    "Транспорт": (
        "transport",
        [
            ("Такси", "taxi"),
            ("Топливо", "fuel"),
        ],
    ),
    "Дом": (
        "home",
        [
            ("Аренда", "rent"),
            ("Коммуналка", "utilities"),
        ],
    ),
    "Прочее": (
        "expense_other",
        [
            ("Другое", "subcategory_other"),
        ],
    ),
}

SEED_WALLETS: list[tuple[str, str, str]] = [
    ("Карта сум", "UZS", "card_uzs"),
    ("Наличный сум", "UZS", "cash_uzs"),
    ("Карта USD", "USD", "card_usd"),
    ("Наличный USD", "USD", "cash_usd"),
]

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


async def copy_seed_data(session: AsyncSession, family_budget_id: uuid.UUID) -> None:
    for name, translation_key in SEED_INCOME_CATEGORIES:
        session.add(
            IncomeCategory(
                family_budget_id=family_budget_id,
                name=name,
                translation_key=translation_key,
            )
        )

    for name, currency, translation_key in SEED_WALLETS:
        session.add(
            Wallet(
                family_budget_id=family_budget_id,
                name=name,
                currency=currency,
                translation_key=translation_key,
            )
        )

    for parent_name, (parent_key, sub_entries) in SEED_EXPENSE_CATEGORIES.items():
        parent = ExpenseCategory(
            family_budget_id=family_budget_id,
            name=parent_name,
            parent_id=None,
            translation_key=parent_key,
        )
        session.add(parent)
        await session.flush()
        for sub_name, sub_key in sub_entries:
            session.add(
                ExpenseCategory(
                    family_budget_id=family_budget_id,
                    name=sub_name,
                    parent_id=parent.id,
                    translation_key=sub_key,
                )
            )


async def count_seed_rows(session: AsyncSession, family_budget_id: uuid.UUID) -> dict[str, int]:
    wallet_count = await session.scalar(
        select(func.count())
        .select_from(Wallet)
        .where(Wallet.family_budget_id == family_budget_id, Wallet.is_deleted.is_(False))
    )
    income_count = await session.scalar(
        select(func.count())
        .select_from(IncomeCategory)
        .where(
            IncomeCategory.family_budget_id == family_budget_id,
            IncomeCategory.is_deleted.is_(False),
        )
    )
    expense_top_count = await session.scalar(
        select(func.count())
        .select_from(ExpenseCategory)
        .where(
            ExpenseCategory.family_budget_id == family_budget_id,
            ExpenseCategory.parent_id.is_(None),
            ExpenseCategory.is_deleted.is_(False),
        )
    )
    expense_sub_count = await session.scalar(
        select(func.count())
        .select_from(ExpenseCategory)
        .where(
            ExpenseCategory.family_budget_id == family_budget_id,
            ExpenseCategory.parent_id.is_not(None),
            ExpenseCategory.is_deleted.is_(False),
        )
    )
    return {
        "wallets": wallet_count or 0,
        "income_categories": income_count or 0,
        "expense_top_level": expense_top_count or 0,
        "expense_subcategories": expense_sub_count or 0,
    }


@router.message(CommandStart())
async def start_handler(
    message: Message, command: CommandObject, state: FSMContext
) -> None:
    if message.from_user is None:
        return

    telegram_id = message.from_user.id
    async with async_session_factory() as session:
        existing_user = await get_active_user_by_telegram_id(session, telegram_id)
        if existing_user is not None:
            await message.answer(t("already_member", existing_user.language))
            return

        flow, invite_token = parse_start_payload(command.args)
        target_budget_id: uuid.UUID | None = None

        if flow == "member":
            assert invite_token is not None
            budget = await get_family_budget_by_invite_token(session, invite_token)
            if budget is None:
                await message.answer(t("invalid_invite", "ru"))
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
                await copy_seed_data(session, budget.id)
            else:
                budget_id = uuid.UUID(data["family_budget_id"])
                user = User(
                    telegram_id=telegram_id,
                    family_budget_id=budget_id,
                    role="member",
                    first_name=data.get("first_name"),
                    username=data.get("username"),
                    language=language,
                )
                session.add(user)

    if existing_language is not None:
        await callback.message.edit_text(t("already_member", existing_language))
        await state.clear()
        await callback.answer()
        return

    if flow == "owner":
        welcome = t("welcome_owner", language)
    else:
        welcome = t("welcome_member", language)

    await callback.message.edit_text(welcome)
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
