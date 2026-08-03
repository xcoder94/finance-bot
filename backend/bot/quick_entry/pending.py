from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quick_entry_pending import QuickEntryPending


async def create_pending(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    family_budget_id: uuid.UUID,
    amount: int,
    currency: Literal["UZS", "USD"],
    wallet_id: uuid.UUID,
    category_raw: str | None,
    comment: str | None,
    operation_date: date,
) -> QuickEntryPending:
    pending = QuickEntryPending(
        user_id=user_id,
        family_budget_id=family_budget_id,
        amount=amount,
        currency=currency,
        wallet_id=wallet_id,
        category_raw=category_raw,
        comment=comment,
        operation_date=operation_date,
    )
    session.add(pending)
    await session.commit()
    await session.refresh(pending)
    return pending
