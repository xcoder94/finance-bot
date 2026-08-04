import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.entity_limits import ENTITY_NAME_MAX, normalize_entity_name

Currency = Literal["UZS", "USD"]


class WalletCreate(BaseModel):
    name: str = Field(max_length=ENTITY_NAME_MAX)
    currency: Currency

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_entity_name(value)


class WalletUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=ENTITY_NAME_MAX)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_entity_name(value)


class WalletResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    currency: str
    translation_key: str | None
    is_personal: bool
    transaction_count: int = Field(default=0)


class WalletDeleteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    currency: str
    affected_transactions_count: int


class IncomeCategoryCreate(BaseModel):
    name: str = Field(max_length=ENTITY_NAME_MAX)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_entity_name(value)


class IncomeCategoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=ENTITY_NAME_MAX)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_entity_name(value)


class IncomeCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    translation_key: str | None
    color_index: int
    transaction_count: int = Field(default=0)


class IncomeCategoryDeleteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    affected_transactions_count: int


class ExpenseCategoryCreate(BaseModel):
    name: str = Field(max_length=ENTITY_NAME_MAX)
    parent_id: uuid.UUID | None = None

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_entity_name(value)


class ExpenseCategoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=ENTITY_NAME_MAX)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_entity_name(value)


class ExpenseCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    translation_key: str | None
    parent_id: uuid.UUID | None
    color_index: int
    transaction_count: int = Field(default=0)


class ExpenseCategoryDeleteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    affected_transactions_count: int
