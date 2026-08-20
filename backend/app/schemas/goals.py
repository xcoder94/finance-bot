import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

# Matches the amount cap in app/schemas/transactions.py (MAX_AMOUNT), which in
# turn matches the bot quick-entry path.
MAX_TARGET_AMOUNT = 2_000_000_000


class GoalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wallet_id: uuid.UUID
    target_amount: int = Field(gt=0, le=MAX_TARGET_AMOUNT)
    name: str | None = None
    deadline: date | None = None


class GoalUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    target_amount: int | None = Field(default=None, gt=0, le=MAX_TARGET_AMOUNT)
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
