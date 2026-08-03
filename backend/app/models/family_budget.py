from datetime import date

from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


DEFAULT_BUDGET_NAME = "Семейный бюджет"


class FamilyBudget(Base, UUIDPrimaryKeyMixin, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "family_budgets"

    name: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=DEFAULT_BUDGET_NAME,
    )
    invite_token: Mapped[str | None] = mapped_column(
        String, nullable=True, unique=True, index=True
    )
    daily_model_calls: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    daily_unparsed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    counters_day: Mapped[date | None] = mapped_column(Date, nullable=True)
