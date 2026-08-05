"""transaction is_demo flag

Revision ID: t0c1d2e3f4a5
Revises: s9b0c1d2e3f4
Create Date: 2026-08-05 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "t0c1d2e3f4a5"
down_revision: Union[str, Sequence[str], None] = "s9b0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "is_demo",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("transactions", "is_demo")
