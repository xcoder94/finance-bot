import secrets
import uuid
from datetime import UTC, datetime
from typing import Annotated

from aiogram import Bot
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.user_deps import CurrentUserDep, OwnerUserDep
from app.config import BOT_TOKEN
from app.db import get_session
from app.models.family_budget import FamilyBudget
from app.models.user import User
from app.schemas.members import InviteLinkResponse, MemberDeleteResponse, MemberResponse
from app.services.invite import (
    build_invite_link,
    cache_bot_username,
    get_cached_bot_username,
)

router = APIRouter(prefix="/api/v1")

async def init_bot_username() -> None:
    bot = Bot(token=BOT_TOKEN)
    try:
        await cache_bot_username(bot)
    finally:
        await bot.session.close()


async def get_bot_username() -> str:
    bot_username = get_cached_bot_username()
    if bot_username is None:
        raise HTTPException(status_code=500)
    return bot_username


async def get_active_family_budget(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
) -> FamilyBudget | None:
    stmt = select(FamilyBudget).where(
        FamilyBudget.id == family_budget_id,
        FamilyBudget.is_deleted.is_(False),
    )
    return await session.scalar(stmt)


async def get_active_member(
    session: AsyncSession,
    member_id: uuid.UUID,
    family_budget_id: uuid.UUID,
) -> User | None:
    stmt = select(User).where(
        User.id == member_id,
        User.family_budget_id == family_budget_id,
        User.is_deleted.is_(False),
    )
    return await session.scalar(stmt)


async def build_invite_link_for_budget(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
) -> str:
    budget = await get_active_family_budget(session, family_budget_id)
    if budget is None or not budget.invite_token:
        raise HTTPException(status_code=404)

    bot_username = await get_bot_username()
    return build_invite_link(bot_username, budget.invite_token)


@router.get("/members")
async def list_members(
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[MemberResponse]:
    stmt = (
        select(User)
        .where(
            User.family_budget_id == user.family_budget_id,
            User.is_deleted.is_(False),
        )
        .order_by(User.created_at)
    )
    members = (await session.scalars(stmt)).all()
    return [
        MemberResponse(
            id=member.id,
            first_name=member.first_name,
            username=member.username,
            role=member.role,
        )
        for member in members
    ]


@router.get("/members/invite-link")
async def get_invite_link(
    user: OwnerUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> InviteLinkResponse:
    invite_link = await build_invite_link_for_budget(session, user.family_budget_id)
    return InviteLinkResponse(invite_link=invite_link)


@router.post("/members/invite-link/regenerate")
async def regenerate_invite_link(
    user: OwnerUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> InviteLinkResponse:
    budget = await get_active_family_budget(session, user.family_budget_id)
    if budget is None:
        raise HTTPException(status_code=404)

    budget.invite_token = secrets.token_urlsafe(16)
    await session.commit()
    await session.refresh(budget)

    bot_username = await get_bot_username()
    return InviteLinkResponse(
        invite_link=build_invite_link(bot_username, budget.invite_token),
    )


@router.delete("/members/{member_id}")
async def delete_member(
    member_id: uuid.UUID,
    user: OwnerUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MemberDeleteResponse:
    if member_id == user.id:
        raise HTTPException(status_code=400, detail="cannot_remove_self")

    member = await get_active_member(session, member_id, user.family_budget_id)
    if member is None:
        raise HTTPException(status_code=404)

    member.is_deleted = True
    member.deleted_at = datetime.now(UTC)
    await session.commit()

    return MemberDeleteResponse(
        id=member.id,
        first_name=member.first_name,
        role=member.role,
    )
