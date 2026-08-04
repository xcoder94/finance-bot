import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TransactionChangeLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "transaction_change_logs"

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False, index=True
    )
    line_text: Mapped[str] = mapped_column(Text, nullable=False)
