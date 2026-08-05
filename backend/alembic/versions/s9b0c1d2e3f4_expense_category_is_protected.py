"""expense category is_protected flag

Revision ID: s9b0c1d2e3f4
Revises: r8a9b0c1d2e3
Create Date: 2026-08-05 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "s9b0c1d2e3f4"
down_revision: Union[str, Sequence[str], None] = "r8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "expense_categories",
        sa.Column(
            "is_protected",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("expense_categories", "is_protected")
