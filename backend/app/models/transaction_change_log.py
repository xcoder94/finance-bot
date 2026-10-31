import uuid
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

_FORMAT_CHECK = """
(format_version = 0 AND line_text IS NOT NULL AND payload IS NULL)
OR (
    format_version = 1
    AND payload IS NOT NULL
    AND jsonb_typeof(payload) = 'object'
    AND payload->>'kind' IN ('created', 'changed')
    AND (
        payload->>'kind' = 'created'
        OR payload->>'field' IN
           ('amount', 'category', 'wallet', 'date', 'comment', 'from', 'to', 'rate')
    )
)
"""


class TransactionChangeLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "transaction_change_logs"
    __table_args__ = (
        CheckConstraint(_FORMAT_CHECK, name="ck_transaction_change_logs_format"),
    )

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False, index=True
    )
    # Legacy Russian text (format_version 0); NULL for new rows.
    line_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    format_version: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default=text("0")
    )
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
