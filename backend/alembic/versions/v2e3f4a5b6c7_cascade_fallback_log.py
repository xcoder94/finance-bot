"""cascade_fallback_log table

Revision ID: v2e3f4a5b6c7
Revises: u1d2e3f4a5b6
Create Date: 2026-08-05 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "u1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cascade_fallback_log",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("family_budget_id", sa.UUID(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["family_budget_id"], ["family_budgets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("cascade_fallback_log")
