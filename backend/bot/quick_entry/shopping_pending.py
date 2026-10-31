"""Bot side of the purchase waiting for a sum (MVP 3, m3-4b).

The app starts a purchase with method receipt/voice and minimises; the next
photo / voice / bare-number text of that user completes it (same service as the
manual path). Unreadable input moves the row to ``unrecognized`` and the user is
sent back to the app for a manual sum.
"""

from __future__ import annotations

import logging
import re

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
    recorded_text,
)
from bot.quick_entry.texts import unparsed_limit_text

logger = logging.getLogger(__name__)

# Operation kinds that can carry "the sum" of a purchase. A bare "412 тысяч" comes
# back from the model as expense or ambiguous; income/transfer never do.
_SUM_TYPES = ("expense", "ambiguous")
# digits, or groups of exactly 3 digits split by space / "." / ","; "1.5" or "412,50" is not a sum
_PLAIN_NUMBER_RE = re.compile(r"^(?:\d+|\d{1,3}(?:[\s.,]\d{3})+)$")


def _usable(amount: int | None) -> bool:
    return amount is not None and 0 < amount <= MAX_AMOUNT


def bare_text_amount(text: str) -> int | None:
    """A message that is only a sum ("412000", "412 000", "412 тысяч")."""
    stripped = text.strip()
    if not stripped:
        return None
    if _PLAIN_NUMBER_RE.match(stripped):
        digits = re.sub(r"[\s.,]", "", stripped)
        value = int(digits)
        return value if _usable(value) else None
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
    return bool(re.match(r"^\d[\d\s.,]*$", stripped)) and bare_text_amount(stripped) is None


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
) -> None:
    """Complete the purchase and answer with the sum + a launcher to the result."""
    try:
        result, _created = await complete_pending_purchase(
            session, user, purchase.id, amount=amount, method=purchase.method or "manual"
        )
    except HTTPException as exc:
        # no wallet / purchase closed in the meantime: the app shows the exact reason
        logger.info("Pending purchase not completed by the bot: %s", exc.detail)
        await session.rollback()
        await message.answer(
            not_recognized_text(user.language),
            reply_markup=launcher_keyboard(user.language, purchase.id),
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
                reply_markup=launcher_keyboard(user.language, purchase_id),
            )
            return
    await session.commit()
    await mark_unrecognized(session, purchase_id)
    await message.answer(
        not_recognized_text(user.language),
        reply_markup=launcher_keyboard(user.language, purchase_id),
    )
