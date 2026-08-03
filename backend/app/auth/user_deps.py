from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AppPassClaimsDep
from app.db import get_session
from app.models.family_budget import FamilyBudget
from app.models.user import User


async def get_current_user(
    claims: AppPassClaimsDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    telegram_id = int(claims["sub"])
    stmt = (
        select(User, FamilyBudget.is_deleted.label("family_is_deleted"))
        .join(FamilyBudget, User.family_budget_id == FamilyBudget.id)
        .where(
            User.telegram_id == telegram_id,
            User.is_deleted.is_(False),
        )
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        raise HTTPException(status_code=401)
    user: User = row[0]
    if row.family_is_deleted:
        raise HTTPException(status_code=403)
    return user


async def require_owner(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if user.role != "owner":
        raise HTTPException(status_code=403)
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
OwnerUserDep = Annotated[User, Depends(require_owner)]
