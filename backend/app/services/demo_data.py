import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.services.transactions import soft_delete_transaction


async def family_has_demo_transactions(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
) -> bool:
    count = await session.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(
            Transaction.family_budget_id == family_budget_id,
            Transaction.is_demo.is_(True),
            Transaction.is_deleted.is_(False),
        )
    )
    return int(count or 0) > 0


async def clear_demo_transactions(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
) -> int:
    transactions = (
        await session.scalars(
            select(Transaction).where(
                Transaction.family_budget_id == family_budget_id,
                Transaction.is_demo.is_(True),
                Transaction.is_deleted.is_(False),
            )
        )
    ).all()
    for transaction in transactions:
        soft_delete_transaction(transaction)
    return len(transactions)
