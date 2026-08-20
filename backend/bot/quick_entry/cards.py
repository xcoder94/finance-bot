from __future__ import annotations

import base64
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


_MARKDOWN_SPECIAL_CHARS = ("_", "*", "`", "[", "]")


def escape_markdown(text: str) -> str:
    """Escape characters aiogram's legacy Markdown parse_mode treats as
    formatting, so user-controlled values (wallet names, category labels,
    comments...) cannot break the parser or inject formatting/links into a
    message that otherwise reads as coming from the bot."""
    escaped = text
    for char in _MARKDOWN_SPECIAL_CHARS:
        escaped = escaped.replace(char, f"\\{char}")
    return escaped


def format_number(amount: int) -> str:
    negative = amount < 0
    digits = str(abs(amount))
    groups: list[str] = []
    while digits:
        groups.insert(0, digits[-3:])
        digits = digits[:-3]
    formatted = " ".join(groups)
    return f"-{formatted}" if negative else formatted


_format_number = format_number


def format_amount(amount: int, currency: str) -> str:
    number = format_number(amount)
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
        f"{sign} **{format_amount(amount, currency)}** · {escape_markdown(category_label)}",
    ]
    if comment:
        lines.append(escape_markdown(comment))
    lines.append(f"{escape_markdown(wallet_name)} · {_format_date(op_date)}")
    lines.append(f"Осталось: {format_amount(balance, currency)}")
    return "\n".join(lines)


def format_transfer_card(
    *,
    amount: int,
    currency: str,
    from_wallet_name: str,
    to_wallet_name: str,
    op_date: date,
    from_balance: int,
    to_balance: int,
) -> str:
    from_bal = _format_number(from_balance)
    to_bal = _format_number(to_balance)
    from_name = escape_markdown(from_wallet_name)
    to_name = escape_markdown(to_wallet_name)
    return "\n".join(
        [
            f"↔️ **{format_amount(amount, currency)}** · Перевод",
            f"{from_name} → {to_name} · {_format_date(op_date)}",
            f"{from_name}: {from_bal} · {to_name}: {to_bal}",
        ]
    )


def format_exchange_card(
    *,
    amount: int,
    from_currency: str,
    to_amount: int,
    to_currency: str,
    rate: int,
    op_date: date,
    from_wallet_name: str,
    to_wallet_name: str,
    from_balance: int,
    to_balance: int,
) -> str:
    amount_from = format_amount(amount, from_currency)
    amount_to = format_amount(to_amount, to_currency)
    from_name = escape_markdown(from_wallet_name)
    to_name = escape_markdown(to_wallet_name)
    return "\n".join(
        [
            f"🔄 **{amount_from} → {amount_to}** · Обмен",
            f"Курс {_format_number(rate)} · {_format_date(op_date)}",
            (
                f"{from_name}: {format_amount(from_balance, from_currency)}"
                f" · {to_name}: {format_amount(to_balance, to_currency)}"
            ),
        ]
    )


def transfer_card_keyboard(transaction_id: uuid.UUID) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
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


_WALLET_SET_PREFIX = "qe:ws:"


def wallet_set_callback_data(
    transaction_id: uuid.UUID, wallet_id: uuid.UUID
) -> str:
    payload = transaction_id.bytes + wallet_id.bytes
    encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"{_WALLET_SET_PREFIX}{encoded}"


def parse_wallet_set_callback(data: str) -> tuple[uuid.UUID, uuid.UUID] | None:
    if not data.startswith(_WALLET_SET_PREFIX):
        return None
    encoded = data[len(_WALLET_SET_PREFIX) :]
    padding = (-len(encoded)) % 4
    if padding:
        encoded += "=" * padding
    try:
        payload = base64.urlsafe_b64decode(encoded)
    except Exception:
        return None
    if len(payload) != 32:
        return None
    try:
        return uuid.UUID(bytes=payload[:16]), uuid.UUID(bytes=payload[16:])
    except ValueError:
        return None


def wallet_picker_keyboard(
    transaction_id: uuid.UUID,
    wallets: list[Wallet],
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=wallet.name,
                    callback_data=wallet_set_callback_data(transaction_id, wallet.id),
                )
            ]
            for wallet in wallets
        ]
    )
