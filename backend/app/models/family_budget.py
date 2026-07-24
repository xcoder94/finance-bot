from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class FamilyBudget(Base, UUIDPrimaryKeyMixin, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "family_budgets"

    invite_token: Mapped[str | None] = mapped_column(
        String, nullable=True, unique=True, index=True
    )
