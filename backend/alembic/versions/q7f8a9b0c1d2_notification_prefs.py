"""notification prefs on users and family_budgets

Revision ID: q7f8a9b0c1d2
Revises: p6e7f8a9b0c1
Create Date: 2026-08-04 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "q7f8a9b0c1d2"
down_revision: Union[str, Sequence[str], None] = "p6e7f8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "evening_reminder_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "weekly_digest_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )
    op.add_column(
        "family_budgets",
        sa.Column("last_evening_reminder_on", sa.Date(), nullable=True),
    )
    op.add_column(
        "family_budgets",
        sa.Column("last_weekly_digest_on", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("family_budgets", "last_weekly_digest_on")
    op.drop_column("family_budgets", "last_evening_reminder_on")
    op.drop_column("users", "weekly_digest_enabled")
    op.drop_column("users", "evening_reminder_enabled")
