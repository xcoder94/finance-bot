import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

_OPEN = "status IN ('awaiting', 'unrecognized')"


class ShoppingItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An ACTIVE item of a family's shopping list. Bought/deleted rows are hard-deleted."""

    __tablename__ = "shopping_items"

    family_budget_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("family_budgets.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    added_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "char_length(name) BETWEEN 1 AND 60 AND name = btrim(name)",
            name="ck_shopping_items_name",
        ),
        Index("uq_shopping_items_family_lname", "family_budget_id", func.lower(name), unique=True),
    )


class ShoppingPurchase(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "shopping_purchases"

    family_budget_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("family_budgets.id", ondelete="CASCADE"), nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    client_token: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="awaiting", server_default="awaiting"
    )
    method: Mapped[str | None] = mapped_column(String(8), nullable=True)
    item_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    bought_item_names: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now() + interval '30 minutes'"),
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "created_by_user_id", "client_token", name="uq_shopping_purchases_user_client_token"
        ),
        UniqueConstraint("transaction_id", name="uq_shopping_purchases_transaction_id"),
        CheckConstraint(
            "status IN ('awaiting', 'unrecognized', 'completed', 'cancelled', 'expired')",
            name="ck_shopping_purchases_status",
        ),
        CheckConstraint(
            "method IS NULL OR method IN ('manual', 'photo', 'voice')",
            name="ck_shopping_purchases_method",
        ),
        CheckConstraint(
            "cardinality(item_ids) BETWEEN 1 AND 100", name="ck_shopping_purchases_item_ids"
        ),
        CheckConstraint("amount IS NULL OR amount > 0", name="ck_shopping_purchases_amount"),
        CheckConstraint(f"({_OPEN}) = (closed_at IS NULL)", name="ck_shopping_purchases_closed_at"),
        CheckConstraint(
            "(status = 'completed') = (transaction_id IS NOT NULL)"
            " AND (status <> 'completed' OR (amount IS NOT NULL"
            " AND bought_item_names IS NOT NULL AND method IS NOT NULL))",
            name="ck_shopping_purchases_completed",
        ),
        Index(
            "uq_shopping_purchases_user_open",
            "created_by_user_id",
            unique=True,
            postgresql_where=text(_OPEN),
        ),
        Index(
            "ix_shopping_purchases_open_expires_at",
            "expires_at",
            postgresql_where=text(_OPEN),
        ),
        Index(
            "ix_shopping_purchases_closed_at",
            "closed_at",
            postgresql_where=text("closed_at IS NOT NULL"),
        ),
    )
