import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Currency = Literal["UZS", "USD"]


class WalletCreate(BaseModel):
    name: str
    currency: Currency


class WalletUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str


class WalletResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    currency: str
    translation_key: str | None
    transaction_count: int = Field(default=0)


class WalletDeleteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    currency: str
    affected_transactions_count: int


class IncomeCategoryCreate(BaseModel):
    name: str


class IncomeCategoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str


class IncomeCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    translation_key: str | None
    transaction_count: int = Field(default=0)


class IncomeCategoryDeleteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    affected_transactions_count: int


class ExpenseCategoryCreate(BaseModel):
    name: str
    parent_id: uuid.UUID | None = None


class ExpenseCategoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str


class ExpenseCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    translation_key: str | None
    parent_id: uuid.UUID | None
    transaction_count: int = Field(default=0)


class ExpenseCategoryDeleteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    affected_transactions_count: int
