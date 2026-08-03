import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class IncomeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_date: datetime
    amount: int = Field(gt=0)
    wallet_id: uuid.UUID
    income_category_id: uuid.UUID
    comment: str | None = Field(default=None, max_length=200)


class ExpenseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_date: datetime
    amount: int = Field(gt=0)
    wallet_id: uuid.UUID
    expense_category_id: uuid.UUID
    comment: str | None = Field(default=None, max_length=200)


class TransferCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_date: datetime
    wallet_id: uuid.UUID
    to_wallet_id: uuid.UUID
    amount: int = Field(gt=0)
    rate: Decimal | None = None
    comment: str | None = Field(default=None, max_length=200)


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
