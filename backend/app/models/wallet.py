import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Wallet(Base, UUIDPrimaryKeyMixin, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "wallets"

    family_budget_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("family_budgets.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    translation_key: Mapped[str | None] = mapped_column(String, nullable=True)
    is_personal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
