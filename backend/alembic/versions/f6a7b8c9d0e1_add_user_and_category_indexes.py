"""add user and expense category indexes

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-23 13:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_users_family_budget_id",
        "users",
        ["family_budget_id"],
        unique=False,
    )
    op.create_index(
        "ix_expense_categories_parent_id_not_null",
        "expense_categories",
        ["parent_id"],
        unique=False,
        postgresql_where=sa.text("parent_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_expense_categories_parent_id_not_null",
        table_name="expense_categories",
    )
    op.drop_index("ix_users_family_budget_id", table_name="users")
