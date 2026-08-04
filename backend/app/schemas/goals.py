import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class GoalCreate(BaseModel):
    wallet_id: uuid.UUID
    target_amount: int = Field(gt=0)
    name: str | None = None
    deadline: date | None = None


class GoalUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    target_amount: int | None = Field(default=None, gt=0)
    deadline: date | None = None


class GoalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    wallet_id: uuid.UUID
    name: str
    target_amount: int
    currency: str
    deadline: date | None
    status: str
    balance: int
    progress_pct: int | None
    excess_amount: int | None
    remaining_amount: int | None
    is_exactly_complete: bool
    closed_at: datetime | None = None
    can_close: bool
