import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict


class MeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    telegram_id: int
    family_budget_id: uuid.UUID
    role: str
    first_name: str | None
    username: str | None
    language: str
    budget_name: str
    member_count: int
    default_wallet_id: uuid.UUID | None
    evening_reminder_enabled: bool
    weekly_digest_enabled: bool
    receipt_photo_enabled: bool


class MeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_wallet_id: uuid.UUID | None = None
    language: Literal["ru", "uz"] | None = None
    evening_reminder_enabled: bool | None = None
    weekly_digest_enabled: bool | None = None


class OnboardingSteps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_operation: bool
    default_wallet_checked: bool
    family_invited: bool


class OnboardingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    show: bool
    steps: OnboardingSteps
