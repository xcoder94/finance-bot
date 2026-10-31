import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserDailyActivity(Base):
    """One row per user per Tashkent day (flags: opened the app / wrote to the bot)."""

    __tablename__ = "user_daily_activity"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    app: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    bot: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")


class AiUsageDaily(Base):
    __tablename__ = "ai_usage_daily"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    model: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(8), primary_key=True)
    outcome: Mapped[str] = mapped_column(String(8), primary_key=True)
    calls: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    calls_no_usage: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    messages: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    input_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    output_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    cost_micro_usd: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")


class AiCostAlert(Base):
    __tablename__ = "ai_cost_alerts"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    threshold_micro_usd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cost_micro_usd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
