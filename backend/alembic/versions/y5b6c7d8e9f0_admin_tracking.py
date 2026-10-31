"""Admin panel: phone, last seen, daily activity, operation channel, AI usage, cost alert

Revision ID: y5b6c7d8e9f0
Revises: x4a5b6c7d8e9
Create Date: 2026-11-01 18:00:00.000000

Contract: work/db/admin-schema.md. Expand-only; existing code keeps working unchanged.
Live-DB safety:
  * every new column is nullable without a default -> catalog-only change, no table rewrite;
  * the CHECK on transactions.channel is added NOT VALID and validated in its own transaction
    (VALIDATE takes SHARE UPDATE EXCLUSIVE, writes keep flowing);
  * indexes on transactions / users / family_budgets are built CONCURRENTLY outside the
    migration transaction (autocommit block). If a concurrent build fails it leaves an INVALID
    index. The autocommit block commits the transactional part first, so a failure inside it
    leaves the columns/tables in place with alembic_version still at x4a5b6c7d8e9. Recovery: run
    the statements of the block by hand (each is idempotent: VALIDATE, DROP INDEX CONCURRENTLY
    IF EXISTS, CREATE INDEX CONCURRENTLY) and `alembic stamp y5b6c7d8e9f0`.
New tables (small, retention purged daily by the 04:00 Tashkent slot):
  user_daily_activity  400 days
  ai_usage_daily       730 days
  ai_cost_alerts       730 days
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "y5b6c7d8e9f0"
down_revision: Union[str, Sequence[str], None] = "x4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CHANNELS = "('text', 'voice', 'photo', 'app')"

# (name, table, definition) -- built CONCURRENTLY
CONCURRENT_INDEXES = [
    (
        "ix_transactions_created_at_channel_live",
        "transactions",
        "(created_at, channel) WHERE is_deleted = false AND is_demo = false",
    ),
    ("ix_users_created_at_id", "users", "(created_at, id)"),
    ("ix_family_budgets_created_at", "family_budgets", "(created_at)"),
]


def upgrade() -> None:
    # --- users: phone, phone prompt, last seen -------------------------------------------
    op.add_column("users", sa.Column("phone", sa.String(20), nullable=True))
    op.add_column("users", sa.Column("phone_shared_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("phone_prompted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "users", sa.Column("phone_prompt_closed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("users", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    # users is small (~20k rows at 10k families): a validating ADD CONSTRAINT scans it in ms.
    op.create_check_constraint(
        "ck_users_phone",
        "users",
        "(phone IS NULL OR phone ~ '^\\+[0-9]{5,19}$') AND (phone IS NULL) = (phone_shared_at IS NULL)",
    )
    op.create_check_constraint(
        "ck_users_phone_prompt",
        "users",
        "phone_prompt_closed_at IS NULL OR phone_prompted_at IS NOT NULL",
    )

    # --- operation channel ---------------------------------------------------------------
    op.add_column("transactions", sa.Column("channel", sa.String(8), nullable=True))
    op.execute(
        f"ALTER TABLE transactions ADD CONSTRAINT ck_transactions_channel "
        f"CHECK (channel IS NULL OR channel IN {CHANNELS}) NOT VALID"
    )
    op.add_column("quick_entry_pending", sa.Column("channel", sa.String(8), nullable=True))
    op.create_check_constraint(
        "ck_quick_entry_pending_channel",
        "quick_entry_pending",
        f"channel IS NULL OR channel IN {CHANNELS}",
    )

    # --- daily activity: one row per (user, Tashkent day) --------------------------------
    op.create_table(
        "user_daily_activity",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("app", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("bot", sa.Boolean(), nullable=False, server_default=sa.false()),
        # (day, user_id): DAU/WAU/MAU/chart/cohorts are day-range scans; the upsert's
        # ON CONFLICT (user_id, day) infers this same unique index (column order irrelevant).
        sa.PrimaryKeyConstraint("day", "user_id", name="pk_user_daily_activity"),
        sa.CheckConstraint("app OR bot", name="ck_user_daily_activity_flag"),
    )

    # --- AI usage daily aggregate --------------------------------------------------------
    op.create_table(
        "ai_usage_daily",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("outcome", sa.String(8), nullable=False),
        sa.Column("calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("calls_no_usage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("messages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("cost_micro_usd", sa.BigInteger(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("day", "model", "kind", "outcome", name="pk_ai_usage_daily"),
        sa.CheckConstraint("kind IN ('text', 'voice', 'photo')", name="ck_ai_usage_daily_kind"),
        sa.CheckConstraint(
            "outcome IN ('ok', 'unparsed', 'error')", name="ck_ai_usage_daily_outcome"
        ),
        sa.CheckConstraint("char_length(model) BETWEEN 1 AND 64", name="ck_ai_usage_daily_model"),
        sa.CheckConstraint(
            "calls >= 0 AND messages >= 0 AND calls_no_usage BETWEEN 0 AND calls"
            " AND input_tokens >= 0 AND output_tokens >= 0 AND cost_micro_usd >= 0",
            name="ck_ai_usage_daily_counters",
        ),
    )

    # --- AI cost alert: at most one per Tashkent day (PK = the race guard) ---------------
    op.create_table(
        "ai_cost_alerts",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("threshold_micro_usd", sa.BigInteger(), nullable=False),
        sa.Column("cost_micro_usd", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("day", name="pk_ai_cost_alerts"),
        sa.CheckConstraint(
            "threshold_micro_usd > 0 AND cost_micro_usd >= threshold_micro_usd",
            name="ck_ai_cost_alerts_values",
        ),
    )

    # --- outside the migration transaction: validate + concurrent indexes ----------------
    with op.get_context().autocommit_block():
        op.execute("ALTER TABLE transactions VALIDATE CONSTRAINT ck_transactions_channel")
        for name, table, definition in CONCURRENT_INDEXES:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
            op.execute(f"CREATE INDEX CONCURRENTLY {name} ON {table} {definition}")


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for name, _table, _definition in reversed(CONCURRENT_INDEXES):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")

    op.drop_table("ai_cost_alerts")
    op.drop_table("ai_usage_daily")
    op.drop_table("user_daily_activity")

    op.drop_constraint("ck_quick_entry_pending_channel", "quick_entry_pending", type_="check")
    op.drop_column("quick_entry_pending", "channel")
    op.drop_constraint("ck_transactions_channel", "transactions", type_="check")
    op.drop_column("transactions", "channel")

    op.drop_constraint("ck_users_phone_prompt", "users", type_="check")
    op.drop_constraint("ck_users_phone", "users", type_="check")
    for column in (
        "last_seen_at",
        "phone_prompt_closed_at",
        "phone_prompted_at",
        "phone_shared_at",
        "phone",
    ):
        op.drop_column("users", column)
