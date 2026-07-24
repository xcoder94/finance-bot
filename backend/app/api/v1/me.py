from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.auth.telegram import TelegramUserDep
from app.db import async_session_factory
from app.models.user import User
from app.schemas.auth import MeResponse

router = APIRouter(prefix="/api/v1")


@router.get("/me")
async def get_me(user: TelegramUserDep) -> MeResponse:
    async with async_session_factory() as session:
        db_user = await session.scalar(
            select(User).where(User.telegram_id == user.id)
        )

    if db_user is None:
        raise HTTPException(status_code=404, detail="not_onboarded")

    if db_user.is_deleted:
        raise HTTPException(status_code=403, detail="removed_from_family")

    return MeResponse(
        id=db_user.id,
        telegram_id=db_user.telegram_id,
        family_budget_id=db_user.family_budget_id,
        role=db_user.role,
        first_name=db_user.first_name,
        username=db_user.username,
        language=db_user.language,
    )
