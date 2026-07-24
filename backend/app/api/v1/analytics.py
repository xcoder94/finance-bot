import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.user_deps import CurrentUserDep
from app.db import get_session
from app.schemas.history_analytics import (
    CategoryAmount,
    Currency,
    SubcategoryAmount,
    SummaryResponse,
    TrendEntry,
    WalletBalancesResponse,
)
from app.services.history_analytics import (
    get_expenses_by_category,
    get_expenses_by_subcategory,
    get_income_by_category,
    get_summary,
    get_trend,
    get_wallet_balances,
    resolve_analytics_date_range,
)

router = APIRouter(prefix="/api/v1/analytics")


@router.get("/expenses-by-category")
async def expenses_by_category(
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
    currency: Annotated[Currency, Query()],
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[CategoryAmount]:
    resolved_from, resolved_to = resolve_analytics_date_range(date_from, date_to)
    return await get_expenses_by_category(
        session,
        user.family_budget_id,
        currency,
        resolved_from,
        resolved_to,
    )


@router.get("/expenses-by-subcategory")
async def expenses_by_subcategory(
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
    parent_category_id: uuid.UUID,
    currency: Annotated[Currency, Query()],
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[SubcategoryAmount]:
    resolved_from, resolved_to = resolve_analytics_date_range(date_from, date_to)
    return await get_expenses_by_subcategory(
        session,
        user.family_budget_id,
        parent_category_id,
        currency,
        resolved_from,
        resolved_to,
    )


@router.get("/income-by-category")
async def income_by_category(
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
    currency: Annotated[Currency, Query()],
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[CategoryAmount]:
    resolved_from, resolved_to = resolve_analytics_date_range(date_from, date_to)
    return await get_income_by_category(
        session,
        user.family_budget_id,
        currency,
        resolved_from,
        resolved_to,
    )


@router.get("/trend")
async def trend(
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[TrendEntry]:
    return await get_trend(session, user.family_budget_id)


@router.get("/summary")
async def summary(
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> SummaryResponse:
    resolved_from, resolved_to = resolve_analytics_date_range(date_from, date_to)
    return await get_summary(
        session,
        user.family_budget_id,
        resolved_from,
        resolved_to,
    )


@router.get("/wallet-balances")
async def wallet_balances(
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WalletBalancesResponse:
    return await get_wallet_balances(session, user.family_budget_id)
