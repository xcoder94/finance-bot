"""MVP 3: shopping list, purchases (awaiting amount), onboarding flags

Designed by db-architect (work/db/m3-schema.md). Place as
backend/alembic/versions/w3f4a5b6c7d8_mvp3_shopping.py without changes.

Revision ID: w3f4a5b6c7d8
Revises: v2e3f4a5b6c7
Create Date: 2026-10-31 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "w3f4a5b6c7d8"
down_revision: Union[str, Sequence[str], None] = "v2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OPEN_STATUSES = "status IN ('awaiting', 'unrecognized')"


def upgrade() -> None:
    # 1. Shopping list: only ACTIVE items live here. Bought / deleted items are
    #    hard-deleted, so the table is capped at 100 rows per family by design.
    op.create_table(
        "shopping_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("family_budget_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("added_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["family_budget_id"], ["family_budgets.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["added_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 60 AND name = btrim(name)",
            name="ck_shopping_items_name",
        ),
    )
    # Serves: list by family, COUNT(*) for the 100 cap, case-insensitive dedup.
    op.create_index(
        "uq_shopping_items_family_lname",
        "shopping_items",
        ["family_budget_id", sa.text("lower(name)")],
        unique=True,
    )

    # 2. Purchases: one row per "Завершить закупку" (manual or awaiting bot).
    op.create_table(
        "shopping_purchases",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("family_budget_id", sa.UUID(), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("client_token", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="awaiting",
            nullable=False,
        ),
        sa.Column("method", sa.String(length=8), nullable=True),
        sa.Column("item_ids", postgresql.ARRAY(sa.UUID()), nullable=False),
        sa.Column("bought_item_names", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=True),
        sa.Column("transaction_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now() + interval '30 minutes'"),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["family_budget_id"], ["family_budgets.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "created_by_user_id",
            "client_token",
            name="uq_shopping_purchases_user_client_token",
        ),
        sa.UniqueConstraint(
            "transaction_id", name="uq_shopping_purchases_transaction_id"
        ),
        sa.CheckConstraint(
            "status IN ('awaiting', 'unrecognized', 'completed', 'cancelled', 'expired')",
            name="ck_shopping_purchases_status",
        ),
        sa.CheckConstraint(
            "method IS NULL OR method IN ('manual', 'photo', 'voice')",
            name="ck_shopping_purchases_method",
        ),
        sa.CheckConstraint(
            "cardinality(item_ids) BETWEEN 1 AND 100",
            name="ck_shopping_purchases_item_ids",
        ),
        sa.CheckConstraint(
            "amount IS NULL OR amount > 0", name="ck_shopping_purchases_amount"
        ),
        # open <=> not closed
        sa.CheckConstraint(
            f"({OPEN_STATUSES}) = (closed_at IS NULL)",
            name="ck_shopping_purchases_closed_at",
        ),
        # completed <=> has the one expense it produced (+ amount, names, method)
        sa.CheckConstraint(
            "(status = 'completed') = (transaction_id IS NOT NULL)"
            " AND (status <> 'completed' OR (amount IS NOT NULL"
            " AND bought_item_names IS NOT NULL AND method IS NOT NULL))",
            name="ck_shopping_purchases_completed",
        ),
    )
    # <= 1 open purchase per user; also the bot's "awaiting purchase of this user" lookup.
    op.create_index(
        "uq_shopping_purchases_user_open",
        "shopping_purchases",
        ["created_by_user_id"],
        unique=True,
        postgresql_where=sa.text(OPEN_STATUSES),
    )
    # Expiry sweeper: open rows past expires_at (tiny partial index).
    op.create_index(
        "ix_shopping_purchases_open_expires_at",
        "shopping_purchases",
        ["expires_at"],
        postgresql_where=sa.text(OPEN_STATUSES),
    )
    # Retention purge: closed rows older than 30 days.
    op.create_index(
        "ix_shopping_purchases_closed_at",
        "shopping_purchases",
        ["closed_at"],
        postgresql_where=sa.text("closed_at IS NOT NULL"),
    )

    # 3. Onboarding O2 flags (nullable ADD COLUMN = metadata-only, no rewrite).
    op.add_column(
        "users",
        sa.Column(
            "default_wallet_screen_opened_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "family_budgets",
        sa.Column(
            "invite_link_opened_at", sa.DateTime(timezone=True), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("family_budgets", "invite_link_opened_at")
    op.drop_column("users", "default_wallet_screen_opened_at")
    op.drop_index(
        "ix_shopping_purchases_closed_at", table_name="shopping_purchases"
    )
    op.drop_index(
        "ix_shopping_purchases_open_expires_at", table_name="shopping_purchases"
    )
    op.drop_index(
        "uq_shopping_purchases_user_open", table_name="shopping_purchases"
    )
    op.drop_table("shopping_purchases")
    op.drop_index("uq_shopping_items_family_lname", table_name="shopping_items")
    op.drop_table("shopping_items")
