from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AppPassClaimsDep
from app.auth.user_deps import CurrentUserDep
from app.db import async_session_factory, get_session
from app.models.family_budget import FamilyBudget
from app.models.user import User
from app.schemas.auth import MeResponse, MeUpdate
from app.services.wallet_visibility import require_wallet_visible
from app.services.wallets_categories import get_active_wallet

router = APIRouter(prefix="/api/v1")


async def _build_me_response(session: AsyncSession, db_user: User) -> MeResponse:
    budget = await session.scalar(
        select(FamilyBudget).where(FamilyBudget.id == db_user.family_budget_id)
    )
    member_count = await session.scalar(
        select(func.count())
        .select_from(User)
        .where(
            User.family_budget_id == db_user.family_budget_id,
            User.is_deleted.is_(False),
        )
    )
    return MeResponse(
        id=db_user.id,
        telegram_id=db_user.telegram_id,
        family_budget_id=db_user.family_budget_id,
        role=db_user.role,
        first_name=db_user.first_name,
        username=db_user.username,
        language=db_user.language,
        budget_name=budget.name if budget is not None else "",
        member_count=member_count or 0,
        default_wallet_id=db_user.default_wallet_id,
    )


@router.get("/me")
async def get_me(claims: AppPassClaimsDep) -> MeResponse:
    telegram_id = int(claims["sub"])
    async with async_session_factory() as session:
        db_user = await session.scalar(
            select(User).where(User.telegram_id == telegram_id)
        )

        if db_user is None:
            raise HTTPException(status_code=404, detail="not_onboarded")

        if db_user.is_deleted:
            raise HTTPException(status_code=403, detail="removed_from_family")

        return await _build_me_response(session, db_user)


@router.patch("/me")
async def patch_me(
    body: MeUpdate,
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MeResponse:
    if "default_wallet_id" in body.model_fields_set:
        if body.default_wallet_id is not None:
            wallet = await get_active_wallet(
                session, body.default_wallet_id, user.family_budget_id
            )
            require_wallet_visible(wallet, user)
            user.default_wallet_id = body.default_wallet_id
        else:
            user.default_wallet_id = None

    if "language" in body.model_fields_set and body.language is not None:
        user.language = body.language

    await session.commit()
    await session.refresh(user)
    return await _build_me_response(session, user)
