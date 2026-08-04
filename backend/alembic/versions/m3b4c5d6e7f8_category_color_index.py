"""category color_index

Revision ID: m3b4c5d6e7f8
Revises: l2a3b4c5d6e7
Create Date: 2026-08-03 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "l2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _backfill_color_index(table_name: str) -> None:
    op.execute(
        sa.text(
            f"""
            WITH ranked AS (
                SELECT
                    id,
                    ((ROW_NUMBER() OVER (
                        PARTITION BY family_budget_id
                        ORDER BY created_at, id
                    ) - 1) % 8) + 1 AS new_color_index
                FROM {table_name}
            )
            UPDATE {table_name} AS target
            SET color_index = ranked.new_color_index
            FROM ranked
            WHERE target.id = ranked.id
            """
        )
    )


def upgrade() -> None:
    for table_name in ("income_categories", "expense_categories"):
        op.add_column(table_name, sa.Column("color_index", sa.Integer(), nullable=True))
        _backfill_color_index(table_name)
        op.alter_column(table_name, "color_index", nullable=False)


def downgrade() -> None:
    op.drop_column("expense_categories", "color_index")
    op.drop_column("income_categories", "color_index")
