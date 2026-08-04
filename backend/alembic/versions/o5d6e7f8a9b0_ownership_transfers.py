"""ownership_transfers table

Revision ID: o5d6e7f8a9b0
Revises: n4c5d6e7f8a9
Create Date: 2026-08-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "o5d6e7f8a9b0"
down_revision: Union[str, Sequence[str], None] = "n4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ownership_transfers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("family_budget_id", sa.UUID(), nullable=False),
        sa.Column("from_user_id", sa.UUID(), nullable=False),
        sa.Column("to_user_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["family_budget_id"], ["family_budgets.id"]),
        sa.ForeignKeyConstraint(["from_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["to_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ownership_transfers_family_budget_id"),
        "ownership_transfers",
        ["family_budget_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ownership_transfers_from_user_id"),
        "ownership_transfers",
        ["from_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ownership_transfers_to_user_id"),
        "ownership_transfers",
        ["to_user_id"],
        unique=False,
    )
    op.create_index(
        "uq_ownership_transfers_one_pending_per_family",
        "ownership_transfers",
        ["family_budget_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_ownership_transfers_one_pending_per_family",
        table_name="ownership_transfers",
    )
    op.drop_index(
        op.f("ix_ownership_transfers_to_user_id"), table_name="ownership_transfers"
    )
    op.drop_index(
        op.f("ix_ownership_transfers_from_user_id"), table_name="ownership_transfers"
    )
    op.drop_index(
        op.f("ix_ownership_transfers_family_budget_id"),
        table_name="ownership_transfers",
    )
    op.drop_table("ownership_transfers")
