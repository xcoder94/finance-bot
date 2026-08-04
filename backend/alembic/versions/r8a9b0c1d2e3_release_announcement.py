"""release announcement delivery marker on users

Revision ID: r8a9b0c1d2e3
Revises: q7f8a9b0c1d2
Create Date: 2026-08-04 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "r8a9b0c1d2e3"
down_revision: Union[str, Sequence[str], None] = "q7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "release_announcement_delivered_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "release_announcement_delivered_at")
