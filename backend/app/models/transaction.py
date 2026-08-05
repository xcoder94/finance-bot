import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Transaction(Base, UUIDPrimaryKeyMixin, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "transactions"

    family_budget_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("family_budgets.id"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String, nullable=False)
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False
    )
    to_wallet_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    to_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rate: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    income_category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("income_categories.id"), nullable=True
    )
    expense_category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("expense_categories.id"), nullable=True
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    transaction_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    is_demo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )


Index(
    "ix_transactions_wallet_id_active",
    Transaction.wallet_id,
    postgresql_where=text("is_deleted = false"),
)
Index(
    "ix_transactions_to_wallet_id_active",
    Transaction.to_wallet_id,
    postgresql_where=text("is_deleted = false AND to_wallet_id IS NOT NULL"),
)
Index(
    "ix_transactions_income_category_id_active",
    Transaction.income_category_id,
    postgresql_where=text(
        "is_deleted = false AND income_category_id IS NOT NULL"
    ),
)
Index(
    "ix_transactions_expense_category_id_active",
    Transaction.expense_category_id,
    postgresql_where=text(
        "is_deleted = false AND expense_category_id IS NOT NULL"
    ),
)
Index(
    "ix_transactions_family_date_id_active",
    Transaction.family_budget_id,
    Transaction.transaction_date.desc(),
    Transaction.id.desc(),
    postgresql_where=text("is_deleted = false"),
)
