"""Bot side of the purchase waiting for a sum (MVP 3, m3-4b).

The app starts a purchase with method receipt/voice and minimises; the next
photo / voice / bare-number text of that user completes it (same service as the
manual path). Unreadable input moves the row to ``unrecognized`` and the user is
sent back to the app for a manual sum.
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal

from aiogram.types import Message
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family_budget import FamilyBudget
from app.models.shopping import ShoppingPurchase
from app.models.user import User
from app.parsing.prefilter import _find_amounts
from app.parsing.types import ParsedOperation, ParseResponse
from app.schemas.transactions import MAX_AMOUNT
from app.services.quick_entry_counters import can_unparsed, spend_unparsed
from app.services.shopping import complete_pending_purchase, mark_unrecognized
from bot.quick_entry.pending_texts import (
    launcher_keyboard,
    not_recognized_text,
    waiting_keyboard,
    recorded_text,
)
from bot.quick_entry.texts import unparsed_limit_text

logger = logging.getLogger(__name__)

# Operation kinds that can carry "the sum" of a purchase. A bare "412 тысяч" comes
# back from the model as expense or ambiguous; income/transfer never do.
_SUM_TYPES = ("expense", "ambiguous")
# digits, or groups of exactly 3 digits split by space / "." / ","; "1.5" or "412,50" is not a sum
_PLAIN_NUMBER_RE = re.compile(r"^(?:\d+|\d{1,3}(?:[\s.,]\d{3})+)$")


_ONLY_DIGITS_AND_SEPARATORS_RE = re.compile(r"^\d[\d\s.,]*$")


# a trailing unit does not change the separator rule: "12 3 сум" is as broken as "12 3".
# Apostrophe in "so'm" may be ASCII, U+02BB, U+02BC, U+2018, U+2019 or a backtick.
_APOS = "['`\u02bb\u02bc\u2018\u2019]"
_CURRENCY_UNIT = rf"(?:сумов|сум|сўм|so{_APOS}m|som|sum|uzs)"
_TRAILING_UNIT_RE = re.compile(rf"^(?P<num>\d[\d\s.,]*?)\s*{_CURRENCY_UNIT}\.?$", re.IGNORECASE)
# "тыс" multiplies, so "412 тыс" is a valid sum; but "12 3 тыс" (digit groups split by a space, not
# groups of 3) is broken exactly like "12 3".
_TRAILING_THOUSAND_RE = re.compile(r"^(?P<num>\d+(?:\s+\d+)+)\s*(?:тысяч[аиу]?|тыс)\.?$", re.IGNORECASE)


# --- spoken / short-hand thousands: "50 ming", "50к", "ellik ming", "пятьдесят тысяч" ---
_THOUSAND_WORDS = {"ming", "минг", "тысяча", "тысячи", "тысяч", "тысячу", "тыс", "k", "к"}
_MILLION_WORDS = {"million", "mln", "миллион", "миллиона", "миллионов", "млн"}
_UNIT_WORDS: dict[str, int] = {}
for _w, _v in (
    ("bir", 1), ("ikki", 2), ("uch", 3), ("tort", 4), ("besh", 5), ("olti", 6), ("yetti", 7),
    ("sakkiz", 8), ("toqqiz", 9), ("on", 10), ("yigirma", 20), ("ottiz", 30), ("qirq", 40),
    ("ellik", 50), ("oltmish", 60), ("yetmish", 70), ("sakson", 80), ("toqson", 90),
    ("один", 1), ("одна", 1), ("два", 2), ("две", 2), ("три", 3), ("четыре", 4), ("пять", 5),
    ("шесть", 6), ("семь", 7), ("восемь", 8), ("девять", 9), ("десять", 10),
    ("одиннадцать", 11), ("двенадцать", 12), ("тринадцать", 13), ("четырнадцать", 14),
    ("пятнадцать", 15), ("шестнадцать", 16), ("семнадцать", 17), ("восемнадцать", 18),
    ("девятнадцать", 19), ("двадцать", 20), ("тридцать", 30), ("сорок", 40),
    ("пятьдесят", 50), ("шестьдесят", 60), ("семьдесят", 70), ("восемьдесят", 80),
    ("девяносто", 90), ("сто", 100), ("двести", 200), ("триста", 300), ("четыреста", 400),
    ("пятьсот", 500), ("шестьсот", 600), ("семьсот", 700), ("восемьсот", 800), ("девятьсот", 900),
):
    _UNIT_WORDS[_w] = _v
_UZ_HUNDRED = "yuz"
_TRAILING_CURRENCY_RE = re.compile(rf"\s*{_CURRENCY_UNIT}\.?$", re.IGNORECASE)
_DIGITS_SCALE_RE = re.compile(r"^(?P<num>\d+(?:[.,]\d{1,2})?)\s*(?P<word>[^\W\d_]+)\.?$", re.IGNORECASE)


def _fold_word(word: str) -> str:
    return re.sub(_APOS, "", word.casefold())


def _multiplier(word: str) -> int | None:
    if word in _THOUSAND_WORDS:
        return 1000
    if word in _MILLION_WORDS:
        return 1_000_000
    return None


def _scaled_amount(text: str) -> int | None:
    """"50 ming", "50к", "ellik ming so'm", "сто пятьдесят тысяч": a sum written with a thousand word.

    Needs a thousand / million word, so a bare "ellik" or a goods name never becomes a sum.
    """
    body = _TRAILING_CURRENCY_RE.sub("", text.strip(), count=1).strip() if text.strip() else ""
    if not body:
        return None
    match = _DIGITS_SCALE_RE.match(body)
    if match:
        mult = _multiplier(_fold_word(match.group("word")))
        if mult is None:
            return None
        value = Decimal(match.group("num").replace(",", ".")) * mult
        return int(value) if value == value.to_integral_value() else None
    total = cur = 0
    seen_mult = False
    tokens = body.replace(",", " ").split()
    for raw in tokens:
        token = _fold_word(raw.rstrip("."))
        mult = _multiplier(token)
        if mult is not None:
            total += (cur or 1) * mult
            cur = 0
            seen_mult = True
        elif token == _UZ_HUNDRED:
            cur = (cur or 1) * 100
        elif token in _UNIT_WORDS:
            cur += _UNIT_WORDS[token]
        else:
            return None
    return total + cur if seen_mult else None


def _digits_part(stripped: str) -> str | None:
    match = _TRAILING_UNIT_RE.match(stripped)
    if match:
        return match.group("num")
    match = _TRAILING_THOUSAND_RE.match(stripped)
    if match and not _PLAIN_NUMBER_RE.match(match.group("num").strip()):
        return match.group("num")
    return None


def _usable(amount: int | None) -> bool:
    return amount is not None and 0 < amount <= MAX_AMOUNT


def bare_text_amount(text: str) -> int | None:
    """A message that is only a sum ("412000", "412 000", "412 тысяч")."""
    stripped = text.strip()
    if not stripped:
        return None
    scaled = _scaled_amount(stripped)
    if scaled is not None:
        return scaled if _usable(scaled) else None
    unit_num = _digits_part(stripped)
    if unit_num is not None:
        # re-run the plain-number rule on the digits alone
        return bare_text_amount(unit_num)
    if _PLAIN_NUMBER_RE.match(stripped):
        digits = re.sub(r"[\s.,]", "", stripped)
        value = int(digits)
        return value if _usable(value) else None
    if _ONLY_DIGITS_AND_SEPARATORS_RE.match(stripped):
        # "12 3", "41 2000", "1.5": digits with a wrong separator layout are never a sum
        return None
    amounts = _find_amounts(stripped)
    if len(amounts) == 1:
        start, end = amounts[0].span
        if not stripped[:start].strip() and not stripped[end:].strip():
            value = amounts[0].value
            return value if _usable(value) else None
    return None


def is_malformed_number(text: str) -> bool:
    """Only digits and separators, but not a valid sum ("1.5", "412,50"): ask again."""
    stripped = text.strip()
    unit_num = _digits_part(stripped)
    if unit_num is not None:
        stripped = unit_num.strip()
    return bool(_ONLY_DIGITS_AND_SEPARATORS_RE.match(stripped)) and bare_text_amount(stripped) is None


def op_sum(ops: list[ParsedOperation]) -> int | None:
    for op in ops:
        if op.type in _SUM_TYPES and _usable(op.amount):
            return op.amount
    return None


def bare_response_amount(response: ParseResponse) -> int | None:
    """Model answer to a text that is just a sum: one operation, no category/comment."""
    if len(response.operations) != 1:
        return None
    op = response.operations[0]
    if op.type not in _SUM_TYPES or op.category or (op.comment or "").strip():
        return None
    return op.amount if _usable(op.amount) else None


async def finish_with_amount(
    message: Message,
    session: AsyncSession,
    user: User,
    purchase: ShoppingPurchase,
    amount: int,
    channel: str,
) -> None:
    """Complete the purchase and answer with the sum + a launcher to the result."""
    try:
        result, _created = await complete_pending_purchase(
            session, user, purchase.id, amount=amount, method=purchase.method or "manual",
            channel=channel,
        )
    except HTTPException as exc:
        # no wallet / purchase closed in the meantime: the app shows the exact reason
        logger.info("Pending purchase not completed by the bot: %s", exc.detail)
        await session.rollback()
        await message.answer(
            not_recognized_text(user.language),
            reply_markup=waiting_keyboard(user.language, purchase.id, launcher=True),
        )
        return
    await message.answer(
        recorded_text(user.language, result.amount),
        reply_markup=launcher_keyboard(user.language, purchase.id),
    )


async def finish_unrecognized(
    message: Message,
    session: AsyncSession,
    user: User,
    budget: FamilyBudget,
    purchase: ShoppingPurchase,
    daily_unparsed_limit: int,
    *,
    counted: bool = False,
) -> None:
    """Nothing usable: manual-sum fallback in the app (counts as «не разобрал»)."""
    purchase_id = purchase.id
    if not counted:
        if can_unparsed(budget, daily_unparsed_limit):
            await spend_unparsed(session, budget)
        else:
            await session.commit()
            await mark_unrecognized(session, purchase_id)
            await message.answer(
                unparsed_limit_text(daily_unparsed_limit),
                reply_markup=waiting_keyboard(user.language, purchase_id, launcher=True),
            )
            return
    await session.commit()
    await mark_unrecognized(session, purchase_id)
    await message.answer(
        not_recognized_text(user.language),
        reply_markup=waiting_keyboard(user.language, purchase_id, launcher=True),
    )


def spoken_response_amount(response: ParseResponse) -> int | None:
    """The sum of a voice answer while a purchase waits for one.

    What the model heard (``transcript``) wins over its own number: it may read "50 ming"
    as 50. Without a usable transcript: the operation amount, then a goods entry that is
    really a sum ("50 ming" taken for an item).
    """
    if response.transcript:
        heard = bare_text_amount(response.transcript)
        if heard is not None:
            return heard
    amount = op_sum(response.operations)
    if amount is not None:
        return amount
    if not response.operations and len(response.shopping_items) == 1:
        return bare_text_amount(response.shopping_items[0])
    return None
