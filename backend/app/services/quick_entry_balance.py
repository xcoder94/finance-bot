from __future__ import annotations

import uuid

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction


async def wallet_balance(session: AsyncSession, wallet_id: uuid.UUID) -> int:
    source_amount = case(
        (
            Transaction.wallet_id == wallet_id,
            case(
                (Transaction.type == "income", Transaction.amount),
                (Transaction.type == "expense", -Transaction.amount),
                (Transaction.type == "transfer", -Transaction.amount),
                else_=0,
            ),
        ),
        else_=0,
    )
    incoming_transfer = case(
        (
            (Transaction.to_wallet_id == wallet_id) & (Transaction.type == "transfer"),
            Transaction.to_amount,
        ),
        else_=0,
    )
    stmt = select(
        func.coalesce(func.sum(source_amount + incoming_transfer), 0)
    ).where(
        Transaction.is_deleted.is_(False),
        or_(
            Transaction.wallet_id == wallet_id,
            Transaction.to_wallet_id == wallet_id,
        ),
    )
    return int(await session.scalar(stmt) or 0)
