import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Matches MAX_AMOUNT/MAX_RATE already enforced on the bot quick-entry path
# (bot/quick_entry/handlers.py, app/services/quick_entry_transfer.py) so both
# entry points accept the same range.
MAX_AMOUNT = 2_000_000_000


class IncomeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_date: datetime
    amount: int = Field(gt=0, le=MAX_AMOUNT)
    wallet_id: uuid.UUID
    income_category_id: uuid.UUID
    comment: str | None = Field(default=None, max_length=200)


class ExpenseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_date: datetime
    amount: int = Field(gt=0, le=MAX_AMOUNT)
    wallet_id: uuid.UUID
    expense_category_id: uuid.UUID
    comment: str | None = Field(default=None, max_length=200)


class TransferCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_date: datetime
    wallet_id: uuid.UUID
    to_wallet_id: uuid.UUID
    amount: int = Field(gt=0, le=MAX_AMOUNT)
    rate: Decimal | None = None
    comment: str | None = Field(default=None, max_length=200)

    @field_validator("rate")
    @classmethod
    def _rate_bounds(cls, value: Decimal | None) -> Decimal | None:
        # Decimal comparisons with NaN/Infinity raise decimal.InvalidOperation
        # instead of returning bool, so is_finite() must be checked before any
        # ordering comparison (including the gt/le Field constraints, which is
        # why those are enforced here manually rather than via Field()).
        if value is None:
            return value
        if not value.is_finite():
            raise ValueError("rate must be a finite number")
        if value <= 0 or value > MAX_AMOUNT:
            raise ValueError(f"rate must be greater than 0 and at most {MAX_AMOUNT}")
        return value


IncomeUpdate = IncomeCreate
ExpenseUpdate = ExpenseCreate
TransferUpdate = TransferCreate


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    transaction_date: datetime
    amount: int
    wallet_id: uuid.UUID
    to_wallet_id: uuid.UUID | None = None
    to_amount: int | None = None
    rate: Decimal | None = None
    income_category_id: uuid.UUID | None = None
    expense_category_id: uuid.UUID | None = None
    comment: str | None = None
    created_by_user_id: uuid.UUID
    changes: list[str] = []
