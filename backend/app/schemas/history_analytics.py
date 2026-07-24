import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Currency = Literal["UZS", "USD"]


class HistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    type: str
    transaction_date: datetime
    amount: int
    currency: str
    wallet_id: uuid.UUID
    wallet_name: str
    wallet_translation_key: str | None = None
    to_wallet_id: uuid.UUID | None = None
    to_wallet_name: str | None = None
    to_wallet_translation_key: str | None = None
    to_amount: int | None = None
    to_currency: str | None = None
    income_category_name: str | None = None
    income_category_translation_key: str | None = None
    expense_category_name: str | None = None
    expense_category_translation_key: str | None = None
    expense_subcategory_name: str | None = None
    expense_subcategory_translation_key: str | None = None
    comment: str | None = None
    created_by: str | None = None


class HistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[HistoryItem]
    total_count: int


class CategoryAmount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: uuid.UUID
    category_name: str
    category_translation_key: str | None = None
    amount: int = Field(ge=0)


class SubcategoryAmount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subcategory_id: uuid.UUID
    subcategory_name: str
    subcategory_translation_key: str | None = None
    amount: int = Field(ge=0)


class TrendEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: str
    currency: str
    income: int = Field(ge=0)
    expense: int = Field(ge=0)


class PerCurrencySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str
    income: int = Field(ge=0)
    expense: int = Field(ge=0)
    transfer_net: int
    net_change: int
    average_daily_expense: int = Field(ge=0)


class SummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    by_currency: list[PerCurrencySummary]
    day_of_week_expense: dict[str, list[int]]
    day_of_week_income: dict[str, list[int]]


class CurrencyBalance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str
    balance: int


class WalletBalancesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    balances: list[CurrencyBalance]
