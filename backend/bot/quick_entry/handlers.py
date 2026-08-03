from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import DAILY_MODEL_CALL_LIMIT, DAILY_UNPARSED_LIMIT
from app.db import async_session_factory
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.income_category import IncomeCategory
from app.models.user import User
from app.models.wallet import Wallet
from app.parsing.base import MessageParser
from app.parsing.factory import get_parser
from app.parsing.types import ParseRequest, ParsedOperation, ParserUnavailable
from app.services.quick_entry_balance import wallet_balance
from app.services.quick_entry_categories import strip_parent_category
from app.services.quick_entry_counters import (
    can_model_call,
    can_unparsed,
    ensure_counters_day,
    spend_model_call,
    spend_unparsed,
    tashkent_today_for_counters,
)
from app.services.quick_entry_create import (
    create_quick_entry_expense,
    create_quick_entry_income,
    resolve_category_id,
)
from app.services.quick_entry_dates import resolve_operation_date, strip_date_words
from app.services.quick_entry_wallets import (
    CurrencyMissing,
    list_wallets_for_parse,
    resolve_wallet,
)
from bot.onboarding import MESSAGES, get_active_user_by_telegram_id
from bot.quick_entry.cards import (
    card_keyboard,
    format_amount,
    format_card,
    type_question_keyboard,
)
from bot.quick_entry.pending import create_pending
from bot.quick_entry.texts import (
    MSG_MODEL_FAIL,
    MSG_NO_AMOUNT,
    MSG_TOO_LONG,
    MSG_TOO_MANY_OPS,
    MSG_TYPE_QUESTION,
    currency_missing_text,
    model_limit_text,
    unparsed_limit_text,
)

router = Router()
TASHKENT = ZoneInfo("Asia/Tashkent")
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


def _is_clear(op: ParsedOperation) -> bool:
    return op.type in ("expense", "income") and op.amount is not None


def _is_ambiguous(op: ParsedOperation) -> bool:
    return op.type == "ambiguous" and op.amount is not None


def _filter_countable(ops: list[ParsedOperation]) -> list[ParsedOperation]:
    return [op for op in ops if op.type not in ("transfer", "exchange")]


def _category_label(category: str | None) -> str:
    if category is None or not category.strip():
        return "Без категории"
    stripped = strip_parent_category(category.strip())
    return stripped if stripped else "Без категории"


def _format_type_question(amount: int, currency: str, category: str | None) -> str:
    line = f"**{format_amount(amount, currency)}**"
    if category is not None and category.strip():
        line += f" · {_category_label(category)}"
    return f"{line}\n{MSG_TYPE_QUESTION}"


def _operation_date_to_datetime(op_date: date) -> datetime:
    return datetime(
        op_date.year,
        op_date.month,
        op_date.day,
        12,
        0,
        tzinfo=TASHKENT,
    )


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


async def handle_quick_entry_text(message: Message, bot: Bot) -> None:
    if message.from_user is None or message.text is None:
        return

    text = message.text.strip()
    if not text:
        return

    telegram_id = message.from_user.id

    async with async_session_factory() as session:
        user = await get_active_user_by_telegram_id(session, telegram_id)
        if user is None:
            await message.answer(MESSAGES["not_registered"]["ru"])
            return

        if len(text) > MAX_MESSAGE_LEN:
            await message.answer(MSG_TOO_LONG)
            return

        budget = await session.get(FamilyBudget, user.family_budget_id)
        if budget is None or budget.is_deleted:
            await message.answer(MESSAGES["not_registered"]["ru"])
            return

        today = tashkent_today_for_counters()
        ensure_counters_day(budget, today)
        if not can_model_call(budget, DAILY_MODEL_CALL_LIMIT):
            await message.answer(model_limit_text(DAILY_MODEL_CALL_LIMIT))
            await session.commit()
            return

        default_wallet = await _get_default_wallet(session, user)
        if default_wallet is None:
            await message.answer(MSG_NO_AMOUNT)
            return

        wallets = await list_wallets_for_parse(session, user.family_budget_id, user)
        parse_request = ParseRequest(
            text=text,
            wallet_names=[w.name for w in wallets],
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
        except ParserUnavailable:
            await message.answer(MSG_MODEL_FAIL)
            await session.commit()
            return

        spend_model_call(budget)
        await session.commit()

        countable = _filter_countable(response.operations)
        if len(countable) > MAX_OPERATIONS:
            if not can_unparsed(budget, DAILY_UNPARSED_LIMIT):
                await message.answer(unparsed_limit_text(DAILY_UNPARSED_LIMIT))
                return
            spend_unparsed(budget)
            await session.commit()
            await message.answer(MSG_TOO_MANY_OPS)
            return

        clear_ops = [op for op in countable if _is_clear(op)]
        ambiguous_ops = [op for op in countable if _is_ambiguous(op)]

        if not clear_ops and not ambiguous_ops:
            if not can_unparsed(budget, DAILY_UNPARSED_LIMIT):
                await message.answer(unparsed_limit_text(DAILY_UNPARSED_LIMIT))
                return
            spend_unparsed(budget)
            await session.commit()
            await message.answer(MSG_NO_AMOUNT)
            return

        op_date = resolve_operation_date(text)
        txn_datetime = _operation_date_to_datetime(op_date)

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
                    await message.answer(unparsed_limit_text(DAILY_UNPARSED_LIMIT))
                    return
                spend_unparsed(budget)
                await session.commit()
                await message.answer(currency_missing_text(resolved.currency))
                continue

            wallet = resolved
            comment = strip_date_words(op.comment, text)
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
                )
                sign = "➕"

            balance = await wallet_balance(session, wallet.id)
            card_text = format_card(
                sign=sign,
                amount=op.amount,
                currency=currency,
                category_label=_category_label(op.category),
                comment=comment,
                wallet_name=wallet.name,
                op_date=op_date,
                balance=balance,
            )
            await message.answer(
                card_text,
                reply_markup=card_keyboard(txn.id),
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
                    await message.answer(unparsed_limit_text(DAILY_UNPARSED_LIMIT))
                    return
                spend_unparsed(budget)
                await session.commit()
                await message.answer(currency_missing_text(resolved.currency))
                continue

            pending = await create_pending(
                session,
                user_id=user.id,
                family_budget_id=user.family_budget_id,
                amount=op.amount,
                currency=currency,
                wallet_id=resolved.id,
                category_raw=op.category,
                comment=strip_date_words(op.comment, text),
                operation_date=op_date,
            )
            await message.answer(
                _format_type_question(op.amount, currency, op.category),
                reply_markup=type_question_keyboard(str(pending.id)),
                parse_mode="Markdown",
            )


@router.message(F.text, ~F.text.startswith("/"))
async def quick_entry_text_handler(message: Message, bot: Bot) -> None:
    await handle_quick_entry_text(message, bot)
