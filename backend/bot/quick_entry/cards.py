from __future__ import annotations

import base64
import uuid
from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.config import MINI_APP_URL
from app.models.wallet import Wallet
from app.services.bot_texts import resolve_language, t
from app.services.display_name import display_name

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


def format_amount(amount: int, currency: str, language: str | None = None) -> str:
    number = format_number(amount)
    if currency == "USD":
        return f"{number} $"
    return f"{number} {t(language, 'card.unit_sum')}"


def _format_date(op_date: date, language: str | None = None) -> str:
    return f"{op_date.day} {t(language, f'month.{op_date.month}')}"


def format_card(
    *,
    sign: str,
    amount: int,
    currency: str,
    category_label: str | None,
    comment: str | None,
    wallet_name: str,
    op_date: date,
    balance: int,
    language: str | None = None,
) -> str:
    """`category_label=None` means no category (shown in the reader's language)."""
    label = category_label if category_label else t(language, "card.no_category")
    lines = [
        f"{sign} **{format_amount(amount, currency, language)}** · {escape_markdown(label)}",
    ]
    if comment:
        lines.append(escape_markdown(comment))
    lines.append(f"{escape_markdown(wallet_name)} · {_format_date(op_date, language)}")
    lines.append(t(language, "card.remaining", amount=format_amount(balance, currency, language)))
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
    language: str | None = None,
) -> str:
    from_bal = _format_number(from_balance)
    to_bal = _format_number(to_balance)
    from_name = escape_markdown(from_wallet_name)
    to_name = escape_markdown(to_wallet_name)
    return "\n".join(
        [
            f"↔️ **{format_amount(amount, currency, language)}** · "
            f"{t(language, 'card.transfer')}",
            f"{from_name} → {to_name} · {_format_date(op_date, language)}",
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
    language: str | None = None,
) -> str:
    amount_from = format_amount(amount, from_currency, language)
    amount_to = format_amount(to_amount, to_currency, language)
    from_name = escape_markdown(from_wallet_name)
    to_name = escape_markdown(to_wallet_name)
    return "\n".join(
        [
            f"🔄 **{amount_from} → {amount_to}** · {t(language, 'card.exchange')}",
            f"{t(language, 'card.rate', rate=_format_number(rate))} · "
            f"{_format_date(op_date, language)}",
            (
                f"{from_name}: {format_amount(from_balance, from_currency, language)}"
                f" · {to_name}: {format_amount(to_balance, to_currency, language)}"
            ),
        ]
    )


def transfer_card_keyboard(
    transaction_id: uuid.UUID, language: str | None = None
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(language, "button.edit"),
                    web_app=WebAppInfo(url=f"{MINI_APP_URL}?tx={transaction_id}"),
                ),
                InlineKeyboardButton(
                    text=t(language, "button.delete"),
                    callback_data=f"qe:del:{transaction_id}",
                ),
            ]
        ]
    )


def card_keyboard(
    transaction_id: uuid.UUID, language: str | None = None
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(language, "button.wallet"),
                    callback_data=f"qe:wal:{transaction_id}",
                ),
                InlineKeyboardButton(
                    text=t(language, "button.edit"),
                    web_app=WebAppInfo(url=f"{MINI_APP_URL}?tx={transaction_id}"),
                ),
                InlineKeyboardButton(
                    text=t(language, "button.delete"),
                    callback_data=f"qe:del:{transaction_id}",
                ),
            ]
        ]
    )


def type_question_keyboard(
    pending_id: str, language: str | None = None
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(language, "button.expense"),
                    callback_data=f"qe:type:{pending_id}:expense",
                ),
                InlineKeyboardButton(
                    text=t(language, "button.income"),
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
    language: str | None = None,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=display_name(wallet.name, wallet.translation_key, language=resolve_language(language)),
                    callback_data=wallet_set_callback_data(transaction_id, wallet.id),
                )
            ]
            for wallet in wallets
        ]
    )
