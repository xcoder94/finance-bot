import uuid

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
