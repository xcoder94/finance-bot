from __future__ import annotations

import base64
import logging
import uuid
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import (
    DAILY_MODEL_CALL_LIMIT,
    DAILY_UNPARSED_LIMIT,
    PARSER_API_KEY,
    PARSER_PROVIDER,
)
from app.db import async_session_factory
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.income_category import IncomeCategory
from app.models.user import User
from app.models.wallet import Wallet
from app.services.family_guard import guard_family_unchanged
from app.parsing.base import MessageParser
from app.parsing.factory import get_parser
from app.services import ai_usage
from app.parsing.types import (
    ParseRequest,
    ParsedOperation,
    ParseResponse,
    ParserMalformed,
    ParserUnavailable,
)
from app.services.goals import check_goal_achievement
from app.services.shopping import find_open_purchase
from app.services.quick_entry_balance import wallet_balance
from app.services.quick_entry_categories import strip_parent_category
from app.services.quick_entry_counters import (
    can_unparsed,
    ensure_counters_day,
    refund_model_call,
    spend_unparsed,
    tashkent_today_for_counters,
    try_spend_model_call,
)
from app.services.quick_entry_create import (
    create_quick_entry_expense,
    resolve_category_id,
)
from app.services.quick_entry_dates import apply_date_hint, strip_date_words
from app.services.quick_entry_wallets import (
    CurrencyMissing,
    list_wallets_for_parse,
    resolve_wallet,
)
from app.services.family_guard import budget_of_user
from bot.onboarding import MESSAGES, get_active_user_by_telegram_id
from bot.quick_entry.shopping_pending import finish_unrecognized, finish_with_amount, op_sum
from bot.quick_entry.cards import card_keyboard, format_card
from app.services.bot_texts import t as catalogue_t
from app.services.display_name import display_name
from bot.quick_entry.texts import (
    model_limit_text,
    unparsed_limit_text,
    currency_missing_text,
)

router = Router()
# Registered instead of `router` while the receipt feature is off, so a photo
# never falls through unanswered.
disabled_router = Router()
logger = logging.getLogger(__name__)
TASHKENT = ZoneInfo("Asia/Tashkent")
MAX_PHOTO_BYTES = 5 * 1024 * 1024

_parser_override: MessageParser | None = None


def set_receipt_parser_override(parser: MessageParser | None) -> None:
    global _parser_override
    _parser_override = parser


def _get_parser() -> MessageParser:
    if _parser_override is not None:
        return _parser_override
    return get_parser()


def _category_label(category: str | None) -> str | None:
    if category is None or not category.strip():
        return None
    stripped = strip_parent_category(category.strip())
    return stripped if stripped else None


async def _receipt_category_label(
    session: AsyncSession, txn: object, language: str | None
) -> str | None:
    category_id = getattr(txn, "expense_category_id", None)
    if category_id is None:
        return None
    category = await session.get(ExpenseCategory, category_id)
    if category is None or category.is_deleted:
        return None
    return display_name(category.name, category.translation_key, language=language or "ru")


def _operation_date_to_datetime(op_date: date) -> datetime:
    return datetime(
        op_date.year,
        op_date.month,
        op_date.day,
        12,
        0,
        tzinfo=TASHKENT,
    )


MAX_COMMENT_LEN = 200
MAX_AMOUNT = 2_000_000_000


def _is_usable_amount(amount: int | None) -> bool:
    return amount is not None and 0 < amount <= MAX_AMOUNT


def _first_expense_op(ops: list[ParsedOperation]) -> ParsedOperation | None:
    for op in ops:
        if op.type == "expense" and _is_usable_amount(op.amount):
            return op
    return None


def _caption_wallet_hint(caption: str | None, op_hint: str | None) -> str | None:
    if not caption:
        return op_hint
    text = caption.strip()
    lowered = text.casefold()
    for prefix in ("с ", "из "):
        if lowered.startswith(prefix):
            text = text[len(prefix):]
            lowered = text.casefold().strip()
            break
    if "налич" in lowered:
        return "наличн"
    if "карт" in lowered:
        return "карт"
    return text.strip()


def _strip_op_comment(op: ParsedOperation, caption: str | None) -> str | None:
    strip_source = caption if caption else (op.comment or "")
    comment = strip_date_words(op.comment, strip_source)
    if comment is None:
        return None
    return comment[:MAX_COMMENT_LEN]


async def _list_expense_category_names(
    session: AsyncSession, family_budget_id: uuid.UUID
) -> list[str]:
    stmt = (
        select(ExpenseCategory.name)
        .where(
            ExpenseCategory.family_budget_id == family_budget_id,
            ExpenseCategory.is_deleted.is_(False),
        )
        .order_by(ExpenseCategory.name)
    )
    return list((await session.scalars(stmt)).all())


async def _list_income_category_names(
    session: AsyncSession, family_budget_id: uuid.UUID
) -> list[str]:
    stmt = (
        select(IncomeCategory.name)
        .where(
            IncomeCategory.family_budget_id == family_budget_id,
            IncomeCategory.is_deleted.is_(False),
        )
        .order_by(IncomeCategory.name)
    )
    return list((await session.scalars(stmt)).all())


async def _get_default_wallet(session: AsyncSession, user: User) -> Wallet | None:
    if user.default_wallet_id is not None:
        wallet = await session.get(Wallet, user.default_wallet_id)
        if wallet is not None and not wallet.is_deleted:
            return wallet
    wallets = await list_wallets_for_parse(session, user.family_budget_id, user)
    return wallets[0] if wallets else None


async def _reply_unreadable(
    message: Message,
    session: AsyncSession,
    budget: FamilyBudget,
    user: User | None = None,
) -> None:
    if not can_unparsed(budget, DAILY_UNPARSED_LIMIT):
        await message.answer(unparsed_limit_text(DAILY_UNPARSED_LIMIT, user.language if user else None))
        return
    await spend_unparsed(session, budget)
    await session.commit()
    await message.answer(catalogue_t(user, "quick.receipt_unreadable"))


async def handle_receipt_photo(message: Message, bot: Bot) -> None:
    if message.from_user is None or not message.photo:
        return

    telegram_id = message.from_user.id
    async with async_session_factory() as session:
        user = await get_active_user_by_telegram_id(session, telegram_id)
        if user is None:
            await message.answer(MESSAGES["not_registered"]["ru"])
            return

        budget = await budget_of_user(session, user)
        if budget is None:
            await message.answer(MESSAGES["not_registered"]["ru"])
            return

        # person's row first (as join/leave do), then the budget's counters: one lock order
        await guard_family_unchanged(session, user)
        today = tashkent_today_for_counters()
        await ensure_counters_day(session, budget, today)

        default_wallet = await _get_default_wallet(session, user)
        open_purchase = await find_open_purchase(session, user.id)
        pending = open_purchase
        if default_wallet is None and pending is None:
            await message.answer(catalogue_t(user, "quick.no_amount"))
            return

        await bot.send_chat_action(chat_id=message.chat.id, action="typing")

        largest = message.photo[-1]
        file = await bot.get_file(largest.file_id)
        if file.file_path is None:
            await message.answer(catalogue_t(user, "quick.model_fail"))
            return
        if file.file_size is not None and file.file_size > MAX_PHOTO_BYTES:
            await message.answer(catalogue_t(user, "quick.model_fail"))
            return
        buffer = await bot.download_file(file.file_path)
        image_bytes = buffer.read() if hasattr(buffer, "read") else bytes(buffer)
        if len(image_bytes) > MAX_PHOTO_BYTES:
            await message.answer(catalogue_t(user, "quick.model_fail"))
            return

        if (PARSER_PROVIDER or "").lower() != "google" or not PARSER_API_KEY:
            await message.answer(catalogue_t(user, "quick.model_fail"))
            return

        granted = await try_spend_model_call(session, budget, DAILY_MODEL_CALL_LIMIT)
        await session.commit()
        if not granted:
            await message.answer(model_limit_text(DAILY_MODEL_CALL_LIMIT, user.language))
            return

        image_b64 = base64.b64encode(image_bytes).decode()
        caption = message.caption

        wallets = await list_wallets_for_parse(session, user.family_budget_id, user)
        parse_request = ParseRequest(
            text=caption or "",
            wallet_names=[w.name for w in wallets],
            expense_category_names=await _list_expense_category_names(
                session, user.family_budget_id
            ),
            income_category_names=await _list_income_category_names(
                session, user.family_budget_id
            ),
            image_base64=image_b64,
            image_mime_type="image/jpeg",
        )

        parser = _get_parser()
        try:
            response = await parser.parse(parse_request)
        except (ParserUnavailable, ParserMalformed) as exc:
            logger.exception(
                "Parser failure entry_path=receipt family_budget_id=%s telegram_user_id=%s: %s",
                user.family_budget_id,
                message.from_user.id,
                exc,
            )
            await refund_model_call(session, budget)
            await message.answer(catalogue_t(user, "quick.model_fail"))
            await session.commit()
            await ai_usage.record_message(None, "photo", "error")
            return

        await ai_usage.record_message(
            None, "photo", ai_usage.message_outcome(response, "photo")
        )
        if response.receipt_status is None:
            await refund_model_call(session, budget)
            await message.answer(catalogue_t(user, "quick.model_fail"))
            await session.commit()
            return

        if pending is not None:
            # The app waits for the purchase total: one sum, no categories/wallets.
            total = (
                None
                if response.receipt_status == "unreadable"
                else op_sum(response.operations)
            )
            if total is None:
                await finish_unrecognized(
                    message, session, user, budget, pending, DAILY_UNPARSED_LIMIT
                )
            else:
                await finish_with_amount(
                    message, session, user, pending, total, channel="photo"
                )
            return

        if response.receipt_status == "unreadable":
            await _reply_unreadable(message, session, budget, user)
            return

        assert default_wallet is not None  # pending purchases returned above
        expense_op = _first_expense_op(response.operations)
        if expense_op is None:
            await _reply_unreadable(message, session, budget, user)
            return

        assert expense_op.amount is not None
        currency: Literal["UZS", "USD"] = (
            expense_op.currency or default_wallet.currency  # type: ignore[assignment]
        )
        effective_hint = _caption_wallet_hint(caption, expense_op.wallet_hint)
        resolved = await resolve_wallet(
            session=session,
            family_budget_id=user.family_budget_id,
            writer=user,
            wallet_hint=effective_hint,
            currency=expense_op.currency,
            default_wallet=default_wallet,
        )
        if isinstance(resolved, CurrencyMissing):
            if not can_unparsed(budget, DAILY_UNPARSED_LIMIT):
                await message.answer(unparsed_limit_text(DAILY_UNPARSED_LIMIT, user.language if user else None))
                return
            await spend_unparsed(session, budget)
            await session.commit()
            await message.answer(currency_missing_text(resolved.currency, user.language))
            return

        wallet = resolved
        currency = wallet.currency  # type: ignore[assignment]
        comment = _strip_op_comment(expense_op, caption)
        category_id = await resolve_category_id(
            session,
            user.family_budget_id,
            op_type="expense",
            category_name=expense_op.category,
        )
        op_date = apply_date_hint(response.date_hint, today)
        txn_datetime = _operation_date_to_datetime(op_date)

        txn = await create_quick_entry_expense(
            session,
            user,
            amount=expense_op.amount,
            wallet_id=wallet.id,
            expense_category_id=category_id,
            comment=comment,
            transaction_date=txn_datetime,
            channel="photo",
        )
        await check_goal_achievement(session, wallet.id, bot=bot)

        balance = await wallet_balance(session, wallet.id)
        card_text = format_card(
            sign="➖",
            amount=expense_op.amount,
            currency=currency,
            category_label=await _receipt_category_label(session, txn, user.language),
            comment=comment,
            wallet_name=display_name(
                wallet.name, wallet.translation_key, language=user.language or "ru"
            ),
            op_date=op_date,
            balance=balance,
            language=user.language,
        )
        await message.answer(
            card_text,
            reply_markup=card_keyboard(txn.id, user.language),
            parse_mode="Markdown",
        )


@router.message(F.photo)
async def receipt_photo_handler(message: Message, bot: Bot) -> None:
    await handle_receipt_photo(message, bot)


@disabled_router.message(F.photo)
async def receipt_photo_disabled_handler(message: Message) -> None:
    user = None
    from_user = getattr(message, "from_user", None)
    if from_user is not None:
        async with async_session_factory() as session:
            user = await get_active_user_by_telegram_id(session, from_user.id)
    await message.answer(catalogue_t(user, "quick.model_fail"))
