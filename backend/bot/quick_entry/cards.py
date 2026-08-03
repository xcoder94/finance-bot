from __future__ import annotations

import uuid
from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.config import MINI_APP_URL
from app.models.wallet import Wallet

_MONTH_GENITIVE = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


def _format_number(amount: int) -> str:
    negative = amount < 0
    digits = str(abs(amount))
    groups: list[str] = []
    while digits:
        groups.insert(0, digits[-3:])
        digits = digits[:-3]
    formatted = " ".join(groups)
    return f"-{formatted}" if negative else formatted


def format_amount(amount: int, currency: str) -> str:
    number = _format_number(amount)
    if currency == "USD":
        return f"{number} $"
    return f"{number} сум"


def _format_date(op_date: date) -> str:
    return f"{op_date.day} {_MONTH_GENITIVE[op_date.month - 1]}"


def format_card(
    *,
    sign: str,
    amount: int,
    currency: str,
    category_label: str,
    comment: str | None,
    wallet_name: str,
    op_date: date,
    balance: int,
) -> str:
    lines = [
        f"{sign} **{format_amount(amount, currency)}** · {category_label}",
    ]
    if comment:
        lines.append(comment)
    lines.append(f"{wallet_name} · {_format_date(op_date)}")
    lines.append(f"Осталось: {format_amount(balance, currency)}")
    return "\n".join(lines)


def card_keyboard(transaction_id: uuid.UUID) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Кошелёк",
                    callback_data=f"qe:wal:{transaction_id}",
                ),
                InlineKeyboardButton(
                    text="Изменить",
                    web_app=WebAppInfo(url=f"{MINI_APP_URL}?tx={transaction_id}"),
                ),
                InlineKeyboardButton(
                    text="Удалить",
                    callback_data=f"qe:del:{transaction_id}",
                ),
            ]
        ]
    )


def type_question_keyboard(pending_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Потратил",
                    callback_data=f"qe:type:{pending_id}:expense",
                ),
                InlineKeyboardButton(
                    text="Получил",
                    callback_data=f"qe:type:{pending_id}:income",
                ),
            ]
        ]
    )


def wallet_picker_keyboard(
    transaction_id: uuid.UUID,
    wallets: list[Wallet],
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=wallet.name,
                    callback_data=f"qe:walset:{transaction_id}:{wallet.id}",
                )
            ]
            for wallet in wallets
        ]
    )
