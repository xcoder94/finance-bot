"""goals table

Revision ID: n4c5d6e7f8a9
Revises: m3b4c5d6e7f8
Create Date: 2026-08-04 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "n4c5d6e7f8a9"
down_revision: Union[str, Sequence[str], None] = "m3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("family_budget_id", sa.UUID(), nullable=False),
        sa.Column("wallet_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("target_amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("crossed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("frozen_balance", sa.Integer(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["family_budget_id"], ["family_budgets.id"]),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_goals_family_budget_id"), "goals", ["family_budget_id"], unique=False
    )
    op.create_index(op.f("ix_goals_wallet_id"), "goals", ["wallet_id"], unique=False)
    op.create_index(
        "uq_goals_one_active_per_wallet",
        "goals",
        ["wallet_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_goals_one_active_per_wallet", table_name="goals")
    op.drop_index(op.f("ix_goals_wallet_id"), table_name="goals")
    op.drop_index(op.f("ix_goals_family_budget_id"), table_name="goals")
    op.drop_table("goals")
