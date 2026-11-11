from __future__ import annotations

import base64
from contextlib import suppress
import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import (
    DAILY_MODEL_CALL_LIMIT,
    DAILY_UNPARSED_LIMIT,
    PARSER_API_KEY,
    PARSER_PROVIDER,
)
from app.db import async_session_factory
from app.models.cascade_fallback_log import CascadeFallbackLog
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.parsing.base import MessageParser
from app.parsing.factory import get_parser
from app.services import ai_usage
from app.parsing.prefilter import PrefilterCategory, build_seed_name_by_key, try_prefilter
from app.parsing.types import (
    ParseRequest,
    ParsedOperation,
    ParseResponse,
    ParserMalformed,
    ParserUnavailable,
)
from app.services.goals import check_goal_achievement
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
    create_quick_entry_income,
    resolve_category_id,
)
from app.services.quick_entry_transfer import (
    create_quick_entry_transfer,
    effective_rate,
    needs_exchange_refusal,
    resolve_transfer_wallets,
)
from app.services.transactions import (
    get_active_transaction,
    get_transaction_wallets,
    require_transaction_modify_permission,
    require_transaction_visible,
    soft_delete_transaction,
)
from app.services.quick_entry_dates import (
    apply_date_hint,
    resolve_operation_date,
    strip_date_words,
)
from app.services.quick_entry_wallets import (
    CurrencyMissing,
    list_wallets_for_parse,
    resolve_wallet,
)
from app.services.bot_texts import t as catalogue_t
from app.services.display_name import display_name
from app.services.shopping import add_shopping_items, cancel_purchase, find_open_purchase
from bot.onboarding import MESSAGES, get_active_user_by_telegram_id, greeting_inline_keyboard
from bot.quick_entry.cards import (
    card_keyboard,
    escape_markdown,
    format_amount,
    format_card,
    format_exchange_card,
    format_number,
    format_transfer_card,
    transfer_card_keyboard,
    type_question_keyboard,
    parse_wallet_set_callback,
    wallet_picker_keyboard,
)
from bot.quick_entry.shopping_pending import (
    bare_response_amount,
    spoken_response_amount,
    is_malformed_number,
    bare_text_amount,
    finish_unrecognized,
    finish_with_amount,
)
from bot.quick_entry.pending_texts import (
    CANCEL_PREFIX,
    already_recorded_text,
    cancelled_text,
)
from bot.quick_entry.pending import consume_pending, create_pending, get_pending
from bot.quick_entry.texts import (
    SHOPPING_ITEMS_PER_MESSAGE,
    currency_missing_text,
    model_limit_text,
    shopping_reply_text,
    unparsed_limit_text,
)

router = Router()
logger = logging.getLogger(__name__)
TASHKENT = ZoneInfo("Asia/Tashkent")
MAX_VOICE_BYTES = 5 * 1024 * 1024
MAX_MESSAGE_LEN = 500
MAX_OPERATIONS = 5

_parser_override: MessageParser | None = None


def set_parser_override(parser: MessageParser | None) -> None:
    global _parser_override
    _parser_override = parser


def _get_parser() -> MessageParser:
    if _parser_override is not None:
        return _parser_override
    return get_parser()


def _resolve_op_date(
    source_text: str, response: ParseResponse, today: date
) -> date:
    if source_text:
        return resolve_operation_date(source_text)
    return apply_date_hint(response.date_hint, today)


def _resolve_rate(op: ParsedOperation, source_text: str) -> int | None:
    if source_text:
        return effective_rate(op, source_text)
    if op.rate is not None and 0 < op.rate <= MAX_AMOUNT:
        return op.rate
    return None


MAX_COMMENT_LEN = 200
MAX_AMOUNT = 2_000_000_000


def _strip_op_comment(op: ParsedOperation, source_text: str) -> str | None:
    strip_source = source_text if source_text else (op.comment or "")
    comment = strip_date_words(op.comment, strip_source)
    if comment is None:
        return None
    return comment[:MAX_COMMENT_LEN]


def _is_usable_amount(amount: int | None) -> bool:
    return amount is not None and 0 < amount <= MAX_AMOUNT


def _is_clear(op: ParsedOperation) -> bool:
    return op.type in ("expense", "income") and _is_usable_amount(op.amount)


def _is_ambiguous(op: ParsedOperation) -> bool:
    return op.type == "ambiguous" and _is_usable_amount(op.amount)


def _is_transfer_op(op: ParsedOperation) -> bool:
    return op.type in ("transfer", "exchange") and _is_usable_amount(op.amount)


def _filter_countable(ops: list[ParsedOperation]) -> list[ParsedOperation]:
    known = ("expense", "income", "ambiguous", "transfer", "exchange")
    return [
        op for op in ops if op.type in known and _is_usable_amount(op.amount)
    ]


def _category_label(category: str | None) -> str | None:
    """Name of the category as the parser returned it; None = no category."""
    if category is None or not category.strip():
        return None
    stripped = strip_parent_category(category.strip())
    return stripped if stripped else None


def _format_type_question(
    amount: int, currency: str, category: str | None, language: str | None = None
) -> str:
    line = f"**{format_amount(amount, currency, language)}**"
    label = _category_label(category)
    if label is not None:
        line += f" · {escape_markdown(label)}"
    return f"{line}\n{catalogue_t(language, 'quick.type_question')}"


def _operation_date_to_datetime(op_date: date) -> datetime:
    return datetime(
        op_date.year,
        op_date.month,
        op_date.day,
        12,
        0,
        tzinfo=TASHKENT,
    )


async def _check_wallets_after_write(
    session: AsyncSession,
    wallet_ids: set[uuid.UUID],
    bot: Bot,
) -> None:
    for wallet_id in wallet_ids:
        await check_goal_achievement(session, wallet_id, bot=bot)


async def _txn_category_label(
    session: AsyncSession, transaction: Transaction, language: str | None = None
) -> str | None:
    """Category name in the reader's language (renamed ones keep the user's own name)."""
    if transaction.type == "expense":
        if transaction.expense_category_id is None:
            return None
        category = await session.get(ExpenseCategory, transaction.expense_category_id)
    else:
        if transaction.income_category_id is None:
            return None
        category = await session.get(IncomeCategory, transaction.income_category_id)
    if category is None or category.is_deleted:
        return None
    return display_name(category.name, category.translation_key, language=language or "ru")


def _wallet_label(wallet: Wallet, language: str | None) -> str:
    return display_name(wallet.name, wallet.translation_key, language=language or "ru")


async def _format_transaction_card(
    session: AsyncSession,
    transaction: Transaction,
    wallet: Wallet,
    language: str | None = None,
) -> str:
    sign = "➖" if transaction.type == "expense" else "➕"
    balance = await wallet_balance(session, wallet.id)
    op_date = transaction.transaction_date.astimezone(TASHKENT).date()
    return format_card(
        sign=sign,
        amount=transaction.amount,
        currency=wallet.currency,  # type: ignore[arg-type]
        category_label=await _txn_category_label(session, transaction, language),
        comment=transaction.comment,
        wallet_name=_wallet_label(wallet, language),
        op_date=op_date,
        balance=balance,
        language=language,
    )


async def _answer_gone(callback: CallbackQuery, who: object = None) -> None:
    """`who`: the User, or just a language code (safe after a rollback)."""
    await callback.answer(catalogue_t(who, "quick.gone"))


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


async def _list_expense_categories_for_prefilter(
    session: AsyncSession, family_budget_id: uuid.UUID
) -> list[PrefilterCategory]:
    stmt = (
        select(ExpenseCategory)
        .where(
            ExpenseCategory.family_budget_id == family_budget_id,
            ExpenseCategory.is_deleted.is_(False),
        )
        .order_by(ExpenseCategory.name)
    )
    rows = (await session.scalars(stmt)).all()
    return [
        PrefilterCategory(
            id=row.id,
            name=row.name,
            translation_key=row.translation_key,
            parent_id=row.parent_id,
        )
        for row in rows
    ]


async def _list_income_categories_for_prefilter(
    session: AsyncSession, family_budget_id: uuid.UUID
) -> list[PrefilterCategory]:
    stmt = (
        select(IncomeCategory)
        .where(
            IncomeCategory.family_budget_id == family_budget_id,
            IncomeCategory.is_deleted.is_(False),
        )
        .order_by(IncomeCategory.name)
    )
    rows = (await session.scalars(stmt)).all()
    return [
        PrefilterCategory(
            id=row.id,
            name=row.name,
            translation_key=row.translation_key,
            parent_id=None,
        )
        for row in rows
    ]


async def _get_default_wallet(session: AsyncSession, user: User) -> Wallet | None:
    if user.default_wallet_id is not None:
        wallet = await session.get(Wallet, user.default_wallet_id)
        if wallet is not None and not wallet.is_deleted:
            return wallet
    wallets = await list_wallets_for_parse(session, user.family_budget_id, user)
    return wallets[0] if wallets else None


async def _try_add_shopping_items(
    message: Message,
    session: AsyncSession,
    user: User,
    budget: FamilyBudget,
    response: ParseResponse,
) -> bool:
    """A parsed message without an amount that is a list of goods goes to the
    family shopping list. Returns True when the message was handled here.
    Messages that also carry a usable operation stay expenses/income."""
    if _filter_countable(response.operations) or not response.shopping_items:
        return False
    names = response.shopping_items[:SHOPPING_ITEMS_PER_MESSAGE]
    result = await add_shopping_items(session, user, names)
    added = [i.name for i in result.added]
    existing = [i.name for i in result.existing]
    if not added and not existing and not result.over_limit:
        return False  # nothing usable (blank names): fall through to "not parsed"
    text = shopping_reply_text(
        user.language,
        added=[escape_markdown(n) for n in added],
        existing=[escape_markdown(n) for n in existing],
        over_limit=bool(result.over_limit),
    )
    await message.answer(
        text, parse_mode="Markdown", reply_markup=greeting_inline_keyboard(user.language),
    )
    return True


def _currency_word(currency: str | None, language: str | None) -> str:
    if currency == "USD":
        return "USD"
    return "сум" if language == "ru" else "so'm"


async def _process_parsed_response(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    user: User,
    budget: FamilyBudget,
    default_wallet: Wallet,
    response: ParseResponse,
    source_text: str,
    today: date,
    *,
    channel: str,
    model_call_granted: bool = False,
) -> None:
    countable = _filter_countable(response.operations)
    clear_ops = [op for op in countable if _is_clear(op)]
    ambiguous_ops = [op for op in countable if _is_ambiguous(op)]
    transfer_ops = [op for op in countable if _is_transfer_op(op)]

    ambiguous_only = (
        not clear_ops
        and not transfer_ops
        and bool(ambiguous_ops)
        and len(countable) <= MAX_OPERATIONS
    )
    # The caller already atomically reserved one daily_model_calls slot
    # (via try_spend_model_call) before invoking the parser, so the counter
    # is already spent here. The only remaining business rule is that an
    # ambiguous-only response is free — refund the reservation for that case.
    if model_call_granted and ambiguous_only:
        await refund_model_call(session, budget)
        await session.commit()

    if len(countable) > MAX_OPERATIONS:
        if not can_unparsed(budget, DAILY_UNPARSED_LIMIT):
            await message.answer(unparsed_limit_text(DAILY_UNPARSED_LIMIT, user.language))
            return
        await spend_unparsed(session, budget)
        await session.commit()
        await message.answer(catalogue_t(user, "quick.too_many_ops"))
        return

    if not clear_ops and not ambiguous_ops and not transfer_ops:
        big_first = next(
            (
                op
                for op in response.operations
                if op.amount is not None and op.amount > MAX_AMOUNT
            ),
            None,
        )
        if big_first is not None:
            await message.answer(
                catalogue_t(
                    user,
                    "quick.amount_too_large",
                    max=format_number(MAX_AMOUNT),
                    cur=_currency_word(
                        big_first.currency or default_wallet.currency, user.language
                    ),
                )
            )
            return
        if not can_unparsed(budget, DAILY_UNPARSED_LIMIT):
            await message.answer(unparsed_limit_text(DAILY_UNPARSED_LIMIT, user.language))
            return
        await spend_unparsed(session, budget)
        await session.commit()
        await message.answer(catalogue_t(user, "quick.no_amount"))
        return

    for big in response.operations:
        if big.amount is not None and big.amount > MAX_AMOUNT:
            what = (big.comment or big.category or "").strip() or (
                "операция" if user.language == "ru" else "amal"
            )
            await message.answer(
                catalogue_t(
                    user,
                    "quick.amount_too_large_partial",
                    what=what[:60],
                    amount=format_number(big.amount),
                    max=format_number(MAX_AMOUNT),
                    cur=_currency_word(
                        big.currency or default_wallet.currency, user.language
                    ),
                )
            )
    op_date = _resolve_op_date(source_text, response, today)
    txn_datetime = _operation_date_to_datetime(op_date)

    for op in transfer_ops:
        assert op.amount is not None
        amount_currency: Literal["UZS", "USD"] = (
            op.currency or default_wallet.currency  # type: ignore[assignment]
        )
        resolved = await resolve_transfer_wallets(
            session=session,
            family_budget_id=user.family_budget_id,
            writer=user,
            from_hint=op.from_wallet_hint,
            to_hint=op.to_wallet_hint,
            amount_currency=amount_currency,
            default_wallet=default_wallet,
        )
        if isinstance(resolved, CurrencyMissing):
            if not can_unparsed(budget, DAILY_UNPARSED_LIMIT):
                await message.answer(unparsed_limit_text(DAILY_UNPARSED_LIMIT, user.language))
                return
            await spend_unparsed(session, budget)
            await session.commit()
            await message.answer(currency_missing_text(resolved.currency, user.language))
            continue

        rate_val = _resolve_rate(op, source_text)
        if needs_exchange_refusal(
            from_currency=resolved.from_wallet.currency,  # type: ignore[arg-type]
            to_currency=resolved.to_wallet.currency,  # type: ignore[arg-type]
            rate=rate_val,
        ):
            if not can_unparsed(budget, DAILY_UNPARSED_LIMIT):
                await message.answer(unparsed_limit_text(DAILY_UNPARSED_LIMIT, user.language))
                return
            await spend_unparsed(session, budget)
            await session.commit()
            await message.answer(catalogue_t(user, "quick.exchange_rate_required"))
            continue

        create_rate = Decimal(rate_val) if rate_val is not None else None
        comment = _strip_op_comment(op, source_text)
        try:
            txn = await create_quick_entry_transfer(
                session,
                user,
                from_wallet_id=resolved.from_wallet.id,
                to_wallet_id=resolved.to_wallet.id,
                amount=op.amount,
                rate=create_rate,
                comment=comment,
                transaction_date=txn_datetime,
                channel=channel,
            )
        except HTTPException:
            if not can_unparsed(budget, DAILY_UNPARSED_LIMIT):
                await message.answer(unparsed_limit_text(DAILY_UNPARSED_LIMIT, user.language))
                return
            await spend_unparsed(session, budget)
            await session.commit()
            await message.answer(catalogue_t(user, "quick.exchange_rate_required"))
            continue

        await _check_wallets_after_write(
            session,
            {resolved.from_wallet.id, resolved.to_wallet.id},
            bot,
        )

        from_balance = await wallet_balance(session, resolved.from_wallet.id)
        to_balance = await wallet_balance(session, resolved.to_wallet.id)
        if (
            resolved.from_wallet.currency != resolved.to_wallet.currency
            and rate_val is not None
        ):
            card_text = format_exchange_card(
                amount=op.amount,
                from_currency=resolved.from_wallet.currency,  # type: ignore[arg-type]
                to_amount=txn.to_amount,
                to_currency=resolved.to_wallet.currency,  # type: ignore[arg-type]
                rate=rate_val,
                op_date=op_date,
                from_wallet_name=_wallet_label(resolved.from_wallet, user.language),
                to_wallet_name=_wallet_label(resolved.to_wallet, user.language),
                from_balance=from_balance,
                to_balance=to_balance,
                language=user.language,
            )
        else:
            card_text = format_transfer_card(
                amount=op.amount,
                currency=amount_currency,
                from_wallet_name=_wallet_label(resolved.from_wallet, user.language),
                to_wallet_name=_wallet_label(resolved.to_wallet, user.language),
                op_date=op_date,
                from_balance=from_balance,
                to_balance=to_balance,
                language=user.language,
            )
        await message.answer(
            card_text,
            reply_markup=transfer_card_keyboard(txn.id, user.language),
            parse_mode="Markdown",
        )

    for op in clear_ops:
        assert op.amount is not None
        currency: Literal["UZS", "USD"] = op.currency or default_wallet.currency  # type: ignore[assignment]
        resolved = await resolve_wallet(
            session=session,
            family_budget_id=user.family_budget_id,
            writer=user,
            wallet_hint=op.wallet_hint,
            currency=op.currency,
            default_wallet=default_wallet,
        )
        if isinstance(resolved, CurrencyMissing):
            if not can_unparsed(budget, DAILY_UNPARSED_LIMIT):
                await message.answer(unparsed_limit_text(DAILY_UNPARSED_LIMIT, user.language))
                return
            await spend_unparsed(session, budget)
            await session.commit()
            await message.answer(currency_missing_text(resolved.currency, user.language))
            continue

        wallet = resolved
        currency = wallet.currency  # type: ignore[assignment]  # card, limits and wallet agree
        comment = _strip_op_comment(op, source_text)
        category_id = await resolve_category_id(
            session,
            user.family_budget_id,
            op_type=op.type,  # type: ignore[arg-type]
            category_name=op.category,
        )

        if op.type == "expense":
            txn = await create_quick_entry_expense(
                session,
                user,
                amount=op.amount,
                wallet_id=wallet.id,
                expense_category_id=category_id,
                comment=comment,
                transaction_date=txn_datetime,
                channel=channel,
            )
            sign = "➖"
        else:
            txn = await create_quick_entry_income(
                session,
                user,
                amount=op.amount,
                wallet_id=wallet.id,
                income_category_id=category_id,
                comment=comment,
                transaction_date=txn_datetime,
                channel=channel,
            )
            sign = "➕"

        await _check_wallets_after_write(session, {wallet.id}, bot)

        balance = await wallet_balance(session, wallet.id)
        card_text = format_card(
            sign=sign,
            amount=op.amount,
            currency=currency,
            category_label=await _txn_category_label(session, txn, user.language),
            comment=comment,
            wallet_name=_wallet_label(wallet, user.language),
            op_date=op_date,
            balance=balance,
            language=user.language,
        )
        await message.answer(
            card_text,
            reply_markup=card_keyboard(txn.id, user.language),
            parse_mode="Markdown",
        )

    for op in ambiguous_ops:
        assert op.amount is not None
        currency = op.currency or default_wallet.currency  # type: ignore[assignment]
        resolved = await resolve_wallet(
            session=session,
            family_budget_id=user.family_budget_id,
            writer=user,
            wallet_hint=op.wallet_hint,
            currency=op.currency,
            default_wallet=default_wallet,
        )
        if isinstance(resolved, CurrencyMissing):
            if not can_unparsed(budget, DAILY_UNPARSED_LIMIT):
                await message.answer(unparsed_limit_text(DAILY_UNPARSED_LIMIT, user.language))
                return
            await spend_unparsed(session, budget)
            await session.commit()
            await message.answer(currency_missing_text(resolved.currency, user.language))
            continue

        currency = resolved.currency  # type: ignore[assignment]
        pending = await create_pending(
            session,
            user_id=user.id,
            family_budget_id=user.family_budget_id,
            amount=op.amount,
            currency=currency,
            wallet_id=resolved.id,
            category_raw=op.category,
            comment=_strip_op_comment(op, source_text),
            operation_date=op_date,
            channel=channel,
            charge_on_confirm=not bool(clear_ops),
        )
        await message.answer(
            _format_type_question(op.amount, currency, op.category, user.language),
            reply_markup=type_question_keyboard(str(pending.id), user.language),
            parse_mode="Markdown",
        )


async def process_quick_entry_text(
    message: Message,
    bot: Bot,
    text: str,
    *,
    prefilter_enabled: bool = False,
) -> None:
    if message.from_user is None:
        return

    telegram_id = message.from_user.id

    async with async_session_factory() as session:
        user = await get_active_user_by_telegram_id(session, telegram_id)
        if user is None:
            await message.answer(MESSAGES["not_registered"]["ru"])
            return

        if len(text) > MAX_MESSAGE_LEN:
            await message.answer(catalogue_t(user, "quick.too_long"))
            return

        budget = await session.get(FamilyBudget, user.family_budget_id)
        if budget is None or budget.is_deleted:
            await message.answer(MESSAGES["not_registered"]["ru"])
            return

        today = tashkent_today_for_counters()
        await ensure_counters_day(session, budget, today)

        # The app is waiting for a purchase sum from this user: a bare amount
        # ("412000") is that sum, not a quick entry.
        open_purchase = await find_open_purchase(session, user.id)
        if open_purchase is not None:
            bare = bare_text_amount(text)
            if bare is not None:
                await finish_with_amount(
                    message, session, user, open_purchase, bare, channel="text"
                )
                return
            if is_malformed_number(text):
                await finish_unrecognized(
                    message, session, user, budget, open_purchase, DAILY_UNPARSED_LIMIT
                )
                return

        # No wallet: money operations are impossible, but a shopping list still
        # works, so the message goes to the parser and is judged afterwards.
        default_wallet = await _get_default_wallet(session, user)

        wallets = await list_wallets_for_parse(session, user.family_budget_id, user)
        wallet_names = [w.name for w in wallets]
        expense_categories = await _list_expense_categories_for_prefilter(
            session, user.family_budget_id
        )
        income_categories = await _list_income_categories_for_prefilter(
            session, user.family_budget_id
        )

        prefilter_op = None
        prefilter_hit = False
        fallback_reason: str = "prefilter_disabled"
        if prefilter_enabled:
            prefilter_result = try_prefilter(
                text,
                wallet_names=wallet_names,
                expense_categories=expense_categories,
                income_categories=income_categories,
                seed_name_by_key=build_seed_name_by_key(),
            )
            prefilter_op = prefilter_result.operation
            prefilter_hit = prefilter_op is not None
            if not prefilter_hit:
                fallback_reason = prefilter_result.reason or "prefilter_disabled"

        if prefilter_hit:
            await ai_usage.record_message("prefilter", "text", "ok")
            if default_wallet is None:
                await message.answer(catalogue_t(user, "quick.no_amount"))
                return
            response = ParseResponse(operations=[prefilter_op])
        else:
            granted = await try_spend_model_call(
                session, budget, DAILY_MODEL_CALL_LIMIT
            )
            await session.commit()
            if not granted:
                await message.answer(model_limit_text(DAILY_MODEL_CALL_LIMIT, user.language))
                return

            # Log only messages that actually reach the parser — a message
            # refused for exhausting the daily limit never gets a row, so the
            # table cannot be grown without bound by refused traffic. Legitimate
            # traffic (anything that proceeds to be parsed) is still logged in
            # full for parser-tuning purposes.
            try:
                async with session.begin_nested():
                    session.add(
                        CascadeFallbackLog(
                            family_budget_id=user.family_budget_id,
                            telegram_user_id=telegram_id,
                            text=text,
                            reason=fallback_reason,
                        )
                    )
                    await session.flush()
            except Exception:
                logger.exception(
                    "Failed to write cascade_fallback_log family_budget_id=%s "
                    "telegram_user_id=%s reason=%s",
                    user.family_budget_id,
                    telegram_id,
                    fallback_reason,
                )

            parse_request = ParseRequest(
                text=text,
                wallet_names=wallet_names,
                expense_category_names=await _list_expense_category_names(
                    session, user.family_budget_id
                ),
                income_category_names=await _list_income_category_names(
                    session, user.family_budget_id
                ),
            )

            parser = _get_parser()
            try:
                response = await parser.parse(parse_request)
            except (ParserUnavailable, ParserMalformed) as exc:
                logger.exception(
                    "Parser failure entry_path=text family_budget_id=%s telegram_user_id=%s: %s",
                    user.family_budget_id,
                    message.from_user.id,
                    exc,
                )
                await refund_model_call(session, budget)
                await message.answer(catalogue_t(user, "quick.model_fail"))
                await session.commit()
                await ai_usage.record_message(None, "text", "error")
                return
            await ai_usage.record_message(
                None, "text", ai_usage.message_outcome(response, "text")
            )

        if open_purchase is not None and not prefilter_hit:
            bare = bare_response_amount(response)
            if bare is not None:
                await finish_with_amount(
                    message, session, user, open_purchase, bare, channel="text"
                )
                return

        if await _try_add_shopping_items(message, session, user, budget, response):
            return
        if default_wallet is None:
            await refund_model_call(session, budget)
            await session.commit()
            await message.answer(catalogue_t(user, "quick.no_amount"))
            return

        await _process_parsed_response(
            message,
            bot,
            session,
            user,
            budget,
            default_wallet,
            response,
            text,
            today,
            channel="text",
            model_call_granted=not prefilter_hit,
        )


async def handle_quick_entry_text(message: Message, bot: Bot) -> None:
    if message.from_user is None or message.text is None:
        return

    text = message.text.strip()
    if not text:
        return

    await process_quick_entry_text(message, bot, text, prefilter_enabled=True)


@router.message(F.text, ~F.text.startswith("/"))
async def quick_entry_text_handler(message: Message, bot: Bot) -> None:
    await handle_quick_entry_text(message, bot)


async def handle_quick_entry_voice(message: Message, bot: Bot) -> None:
    if message.from_user is None or message.voice is None:
        return

    telegram_id = message.from_user.id
    async with async_session_factory() as session:
        user = await get_active_user_by_telegram_id(session, telegram_id)
        if user is None:
            await message.answer(MESSAGES["not_registered"]["ru"])
            return

        budget = await session.get(FamilyBudget, user.family_budget_id)
        if budget is None or budget.is_deleted:
            await message.answer(MESSAGES["not_registered"]["ru"])
            return

        today = tashkent_today_for_counters()
        await ensure_counters_day(session, budget, today)

        default_wallet = await _get_default_wallet(session, user)
        open_purchase = await find_open_purchase(session, user.id)
        pending = open_purchase

        await bot.send_chat_action(chat_id=message.chat.id, action="typing")

        file = await bot.get_file(message.voice.file_id)
        if file.file_path is None:
            await message.answer(catalogue_t(user, "quick.model_fail"))
            return
        if file.file_size is not None and file.file_size > MAX_VOICE_BYTES:
            await message.answer(catalogue_t(user, "quick.model_fail"))
            return
        buffer = await bot.download_file(file.file_path)
        audio = buffer.read() if hasattr(buffer, "read") else bytes(buffer)
        if len(audio) > MAX_VOICE_BYTES:
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

        audio_b64 = base64.b64encode(audio).decode()

        wallets = await list_wallets_for_parse(session, user.family_budget_id, user)
        parse_request = ParseRequest(
            text="",
            wallet_names=[w.name for w in wallets],
            expense_category_names=await _list_expense_category_names(
                session, user.family_budget_id
            ),
            income_category_names=await _list_income_category_names(
                session, user.family_budget_id
            ),
            audio_base64=audio_b64,
            audio_mime_type="audio/ogg",
        )

        parser = _get_parser()
        try:
            response = await parser.parse(parse_request)
        except (ParserUnavailable, ParserMalformed) as exc:
            logger.exception(
                "Parser failure entry_path=voice family_budget_id=%s telegram_user_id=%s: %s",
                user.family_budget_id,
                message.from_user.id,
                exc,
            )
            await refund_model_call(session, budget)
            await message.answer(catalogue_t(user, "quick.model_fail"))
            await session.commit()
            await ai_usage.record_message(None, "voice", "error")
            return

        await ai_usage.record_message(
            None, "voice", ai_usage.message_outcome(response, "voice")
        )
        if response.speech_status is None:
            await refund_model_call(session, budget)
            await message.answer(catalogue_t(user, "quick.model_fail"))
            await session.commit()
            return

        if response.speech_status == "not_recognized":
            await refund_model_call(session, budget)
            if pending is not None:
                await finish_unrecognized(
                    message, session, user, budget, pending, DAILY_UNPARSED_LIMIT
                )
                return
            if not can_unparsed(budget, DAILY_UNPARSED_LIMIT):
                await message.answer(unparsed_limit_text(DAILY_UNPARSED_LIMIT, user.language))
                await session.commit()
                return
            await spend_unparsed(session, budget)
            await session.commit()
            await message.answer(catalogue_t(user, "quick.voice_not_recognized"))
            return

        if pending is not None:
            amount = spoken_response_amount(response)
            if amount is None:
                await finish_unrecognized(
                    message, session, user, budget, pending, DAILY_UNPARSED_LIMIT
                )
            else:
                await finish_with_amount(
                    message, session, user, pending, amount, channel="voice"
                )
            return

        if await _try_add_shopping_items(message, session, user, budget, response):
            return
        if default_wallet is None:
            await refund_model_call(session, budget)
            await session.commit()
            await message.answer(catalogue_t(user, "quick.no_amount"))
            return

        await _process_parsed_response(
            message,
            bot,
            session,
            user,
            budget,
            default_wallet,
            response,
            "",
            today,
            channel="voice",
            model_call_granted=True,
        )


@router.message(F.voice)
async def quick_entry_voice_handler(message: Message, bot: Bot) -> None:
    await handle_quick_entry_voice(message, bot)


async def handle_quick_entry_delete(callback: CallbackQuery, bot: Bot) -> None:
    if callback.from_user is None or callback.message is None or callback.data is None:
        return

    try:
        txn_id = uuid.UUID(callback.data.split(":", 2)[2])
    except (IndexError, ValueError):
        return

    async with async_session_factory() as session:
        user = await get_active_user_by_telegram_id(session, callback.from_user.id)
        if user is None:
            await _answer_gone(callback, user)
            return

        transaction = await get_active_transaction(
            session, txn_id, user.family_budget_id
        )
        if transaction is None:
            await _answer_gone(callback, user)
            return

        from_wallet, to_wallet = await get_transaction_wallets(
            session, transaction, user.family_budget_id
        )
        try:
            require_transaction_modify_permission(
                user, transaction, from_wallet, to_wallet
            )
        except HTTPException:
            await _answer_gone(callback, user)
            return

        soft_delete_transaction(transaction)
        await session.commit()
        affected = {transaction.wallet_id}
        if transaction.to_wallet_id is not None:
            affected.add(transaction.to_wallet_id)
        await _check_wallets_after_write(session, affected, bot)
        await callback.answer()
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            pass


async def handle_quick_entry_wallet_list(callback: CallbackQuery, bot: Bot) -> None:
    if callback.from_user is None or callback.message is None or callback.data is None:
        return

    try:
        txn_id = uuid.UUID(callback.data.split(":", 2)[2])
    except (IndexError, ValueError):
        return

    async with async_session_factory() as session:
        user = await get_active_user_by_telegram_id(session, callback.from_user.id)
        if user is None:
            await _answer_gone(callback, user)
            return

        transaction = await get_active_transaction(
            session, txn_id, user.family_budget_id
        )
        if transaction is None:
            await _answer_gone(callback, user)
            return

        from_wallet, to_wallet = await get_transaction_wallets(
            session, transaction, user.family_budget_id
        )
        try:
            require_transaction_modify_permission(
                user, transaction, from_wallet, to_wallet
            )
        except HTTPException:
            await _answer_gone(callback, user)
            return

        wallets = await list_wallets_for_parse(session, user.family_budget_id, user)
        await callback.message.edit_reply_markup(
            reply_markup=wallet_picker_keyboard(transaction.id, wallets, user.language)
        )
        await callback.answer()


async def handle_quick_entry_wallet_set(callback: CallbackQuery, bot: Bot) -> None:
    if callback.from_user is None or callback.message is None or callback.data is None:
        return

    parsed = parse_wallet_set_callback(callback.data)
    if parsed is None:
        return

    txn_id, wallet_id = parsed

    async with async_session_factory() as session:
        user = await get_active_user_by_telegram_id(session, callback.from_user.id)
        if user is None:
            await _answer_gone(callback, user)
            return

        transaction = await get_active_transaction(
            session, txn_id, user.family_budget_id
        )
        if transaction is None:
            await _answer_gone(callback, user)
            return

        from_wallet, to_wallet = await get_transaction_wallets(
            session, transaction, user.family_budget_id
        )
        try:
            require_transaction_modify_permission(
                user, transaction, from_wallet, to_wallet
            )
        except HTTPException:
            await _answer_gone(callback, user)
            return

        wallets = await list_wallets_for_parse(session, user.family_budget_id, user)
        wallet = next((w for w in wallets if w.id == wallet_id), None)
        if wallet is None:
            await _answer_gone(callback, user)
            return

        old_wallet_id = transaction.wallet_id
        transaction.wallet_id = wallet.id
        await session.commit()
        await session.refresh(transaction)
        await _check_wallets_after_write(
            session,
            {old_wallet_id, wallet.id},
            bot,
        )

        card_text = await _format_transaction_card(
            session, transaction, wallet, user.language
        )
        await callback.message.edit_text(
            card_text,
            reply_markup=card_keyboard(transaction.id, user.language),
            parse_mode="Markdown",
        )
        await callback.answer()


async def handle_quick_entry_type(callback: CallbackQuery, bot: Bot) -> None:
    if callback.from_user is None or callback.message is None or callback.data is None:
        return

    parts = callback.data.split(":")
    if len(parts) != 4:
        return

    try:
        pending_id = uuid.UUID(parts[2])
    except ValueError:
        return

    choice = parts[3]
    if choice not in ("expense", "income"):
        return

    async with async_session_factory() as session:
        user = await get_active_user_by_telegram_id(session, callback.from_user.id)
        if user is None:
            await _answer_gone(callback, user)
            return

        pending = await get_pending(session, pending_id)
        if pending is None or pending.user_id != user.id:
            await _answer_gone(callback, user)
            return

        budget = await session.get(FamilyBudget, user.family_budget_id)
        if budget is None or budget.is_deleted:
            await _answer_gone(callback, user)
            return

        today = tashkent_today_for_counters()
        await ensure_counters_day(session, budget, today)

        if pending.charge_on_confirm:
            granted = await try_spend_model_call(
                session, budget, DAILY_MODEL_CALL_LIMIT
            )
            await session.commit()
            if not granted:
                await callback.answer(model_limit_text(DAILY_MODEL_CALL_LIMIT, user.language))
                return

        consumed = await consume_pending(session, pending_id)
        if consumed is None:
            if pending.charge_on_confirm:
                await refund_model_call(session, budget)
                await session.commit()
            await _answer_gone(callback, user)
            return

        txn_datetime = _operation_date_to_datetime(consumed.operation_date)
        category_id = await resolve_category_id(
            session,
            user.family_budget_id,
            op_type=choice,  # type: ignore[arg-type]
            category_name=consumed.category_raw,
            button_choice=choice,  # type: ignore[arg-type]
        )

        if choice == "expense":
            txn = await create_quick_entry_expense(
                session,
                user,
                amount=consumed.amount,
                wallet_id=consumed.wallet_id,
                expense_category_id=category_id,
                comment=consumed.comment,
                transaction_date=txn_datetime,
                channel=consumed.channel,
            )
        else:
            txn = await create_quick_entry_income(
                session,
                user,
                amount=consumed.amount,
                wallet_id=consumed.wallet_id,
                income_category_id=category_id,
                comment=consumed.comment,
                transaction_date=txn_datetime,
                channel=consumed.channel,
            )

        wallet = await session.get(Wallet, consumed.wallet_id)
        if wallet is None:
            await _answer_gone(callback, user)
            return

        await _check_wallets_after_write(session, {consumed.wallet_id}, bot)

        card_text = await _format_transaction_card(session, txn, wallet, user.language)
        await callback.message.edit_text(
            card_text,
            reply_markup=card_keyboard(txn.id, user.language),
            parse_mode="Markdown",
        )
        await callback.answer()


async def handle_purchase_cancel(callback: CallbackQuery) -> None:
    """«Отменить закупку» under the wait-for-sum messages."""
    if callback.from_user is None or callback.data is None:
        return
    try:
        purchase_id = uuid.UUID(callback.data.removeprefix(CANCEL_PREFIX))
    except ValueError:
        await callback.answer()
        return
    async with async_session_factory() as session:
        user = await get_active_user_by_telegram_id(session, callback.from_user.id)
        if user is None:
            await _answer_gone(callback, user)
            return
        language = user.language
        try:
            await cancel_purchase(session, user, purchase_id)
            text = cancelled_text(language)
        except HTTPException as exc:
            await session.rollback()
            if exc.status_code != 410:
                await _answer_gone(callback, language)
                return
            text = already_recorded_text(language)
    await callback.answer()
    if callback.message is not None:
        with suppress(Exception):
            await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(text)


@router.callback_query(F.data.startswith(CANCEL_PREFIX))
async def purchase_cancel_callback(callback: CallbackQuery) -> None:
    await handle_purchase_cancel(callback)


@router.callback_query(F.data.startswith("qe:del:"))
async def quick_entry_delete_callback(callback: CallbackQuery, bot: Bot) -> None:
    await handle_quick_entry_delete(callback, bot)


@router.callback_query(F.data.startswith("qe:wal:"))
async def quick_entry_wallet_list_callback(callback: CallbackQuery, bot: Bot) -> None:
    await handle_quick_entry_wallet_list(callback, bot)


@router.callback_query(F.data.startswith("qe:ws:"))
async def quick_entry_wallet_set_callback(callback: CallbackQuery, bot: Bot) -> None:
    await handle_quick_entry_wallet_set(callback, bot)


@router.callback_query(F.data.startswith("qe:type:"))
async def quick_entry_type_callback(callback: CallbackQuery, bot: Bot) -> None:
    await handle_quick_entry_type(callback, bot)
