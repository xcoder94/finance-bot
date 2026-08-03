"""family budget name

Revision ID: l2a3b4c5d6e7
Revises: k1f2a3b4c5d6
Create Date: 2026-08-03 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l2a3b4c5d6e7"
down_revision: Union[str, Sequence[str], None] = "k1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_BUDGET_NAME = "Семейный бюджет"


def upgrade() -> None:
    op.add_column(
        "family_budgets",
        sa.Column(
            "name",
            sa.String(30),
            server_default=DEFAULT_BUDGET_NAME,
            nullable=False,
        ),
    )
    op.execute(
        sa.text("UPDATE family_budgets SET name = :name").bindparams(
            name=DEFAULT_BUDGET_NAME
        )
    )


def downgrade() -> None:
    op.drop_column("family_budgets", "name")
