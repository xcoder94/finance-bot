import unicodedata
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

from app.schemas.transactions import MAX_AMOUNT

ITEM_NAME_MAX = 60
PURCHASE_ITEMS_MAX = 100


def normalize_item_name(name: str) -> str:
    """Trim and collapse inner whitespace; raises ValueError if empty or too long."""
    normalized = " ".join(name.split())
    if not normalized:
        raise ValueError("name must not be empty")
    if any(unicodedata.category(ch) in ("Cc", "Cs") for ch in normalized):
        raise ValueError("name must not contain control characters")
    if len(normalized) > ITEM_NAME_MAX:
        raise ValueError(f"name must be at most {ITEM_NAME_MAX} characters")
    return normalized


class ShoppingItemBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return normalize_item_name(value)


class ShoppingItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    created_at: datetime


class PurchaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_ids: list[uuid.UUID] = Field(min_length=1, max_length=PURCHASE_ITEMS_MAX)
    amount: int = Field(gt=0, le=MAX_AMOUNT)
    client_token: uuid.UUID


class PurchaseResult(BaseModel):
    id: uuid.UUID
    transaction_id: uuid.UUID
    items_recorded: int
    amount: int
    currency: str
    category_label: str
    wallet_name: str
    remaining: int
    items_left: int


class PendingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_ids: list[uuid.UUID] = Field(min_length=1, max_length=PURCHASE_ITEMS_MAX)
    method: Literal["receipt", "voice"]
    # optional: a retry after a network failure returns the same waiting row
    client_token: uuid.UUID | None = None


class PendingAmount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: StrictInt = Field(gt=0, le=MAX_AMOUNT)


class PendingStatus(BaseModel):
    id: uuid.UUID
    # awaiting | unrecognized | completed | cancelled | expired
    status: str
    # receipt | voice | manual
    method: str | None
    expires_at: datetime
    # equals id once completed (GET /purchases/{id} then returns the result)
    purchase_id: uuid.UUID | None
    amount: int | None
