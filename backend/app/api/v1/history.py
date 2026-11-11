import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.user_deps import CurrentUserDep
from app.db import get_session
from app.schemas.history_analytics import Currency, HistoryResponse
from app.services.wallet_visibility import require_wallet_visible
from app.services.wallets_categories import get_active_wallet
from app.services.history_analytics import as_utc, get_history, should_include_created_by

router = APIRouter(prefix="/api/v1")


@router.get("/transactions/history")
async def list_transaction_history(
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
    date_from: datetime,
    date_to: datetime,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    expense_category_id: uuid.UUID | None = None,
    wallet_id: uuid.UUID | None = None,
    uncategorized: bool = False,
    currency: Currency | None = None,
) -> HistoryResponse:
    date_from, date_to = as_utc(date_from), as_utc(date_to)
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to")
    if wallet_id is not None:
        wallet = await get_active_wallet(session, wallet_id, user.family_budget_id)
        require_wallet_visible(wallet, user)
    include_created_by = await should_include_created_by(session, user.family_budget_id)
    items, total_count = await get_history(
        session,
        user.family_budget_id,
        user,
        date_from,
        date_to,
        limit,
        offset,
        include_created_by,
        expense_category_id,
        wallet_id,
        uncategorized,
        currency,
    )
    serialized_items = [
        item.model_dump() if include_created_by else item.model_dump(exclude={"created_by"})
        for item in items
    ]
    return HistoryResponse.model_validate({"items": serialized_items, "total_count": total_count})
