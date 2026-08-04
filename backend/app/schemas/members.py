import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str | None
    username: str | None
    role: str
    created_at: datetime


class InviteLinkResponse(BaseModel):
    invite_link: str


class MemberDeleteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str | None
    role: str


class TransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    to_user_id: uuid.UUID
    status: str
