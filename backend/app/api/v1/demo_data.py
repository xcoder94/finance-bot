from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.user_deps import OwnerUserDep
from app.db import get_session
from app.services.demo_data import clear_demo_transactions, family_has_demo_transactions

router = APIRouter(prefix="/api/v1")


class DemoDataStatusResponse(BaseModel):
    has_demo_data: bool


class DemoDataClearResponse(BaseModel):
    cleared_count: int


@router.get("/demo-data/status")
async def get_demo_data_status(
    user: OwnerUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DemoDataStatusResponse:
    has_demo = await family_has_demo_transactions(session, user.family_budget_id)
    return DemoDataStatusResponse(has_demo_data=has_demo)


@router.delete("/demo-data")
async def delete_demo_data(
    user: OwnerUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DemoDataClearResponse:
    cleared_count = await clear_demo_transactions(session, user.family_budget_id)
    await session.commit()
    return DemoDataClearResponse(cleared_count=cleared_count)
