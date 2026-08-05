import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SupportMessage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "support_messages"

    forwarded_message_id: Mapped[int] = mapped_column(
        Integer, nullable=False, unique=True, index=True
    )
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    family_budget_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("family_budgets.id"), nullable=False
    )
