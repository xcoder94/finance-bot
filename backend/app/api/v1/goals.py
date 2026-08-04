import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.user_deps import CurrentUserDep, OwnerUserDep
from app.db import get_session
from app.schemas.goals import GoalCreate, GoalResponse, GoalUpdate
from app.services.goals import close_goal, create_goal, list_goals, update_goal

router = APIRouter(prefix="/api/v1")


@router.get("/goals")
async def get_goals(
    status: Literal["active", "closed"],
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[GoalResponse]:
    return await list_goals(session, user, status)


@router.post("/goals", status_code=201)
async def post_goal(
    body: GoalCreate,
    user: OwnerUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GoalResponse:
    return await create_goal(session, user, body)


@router.patch("/goals/{goal_id}")
async def patch_goal(
    goal_id: uuid.UUID,
    body: GoalUpdate,
    user: OwnerUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GoalResponse:
    return await update_goal(session, user, goal_id, body)


@router.post("/goals/{goal_id}/close")
async def post_close_goal(
    goal_id: uuid.UUID,
    user: OwnerUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GoalResponse:
    return await close_goal(session, user, goal_id)
