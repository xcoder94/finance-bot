from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.auth.deps import AppPassClaimsDep
from app.db import async_session_factory
from app.models.family_budget import FamilyBudget
from app.models.user import User
from app.schemas.auth import MeResponse

router = APIRouter(prefix="/api/v1")


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
