"""add transaction query indexes

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-23 11:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_transactions_wallet_id_active",
        "transactions",
        ["wallet_id"],
        unique=False,
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ix_transactions_to_wallet_id_active",
        "transactions",
        ["to_wallet_id"],
        unique=False,
        postgresql_where=sa.text(
            "is_deleted = false AND to_wallet_id IS NOT NULL"
        ),
    )
    op.create_index(
        "ix_transactions_income_category_id_active",
        "transactions",
        ["income_category_id"],
        unique=False,
        postgresql_where=sa.text(
            "is_deleted = false AND income_category_id IS NOT NULL"
        ),
    )
    op.create_index(
        "ix_transactions_expense_category_id_active",
        "transactions",
        ["expense_category_id"],
        unique=False,
        postgresql_where=sa.text(
            "is_deleted = false AND expense_category_id IS NOT NULL"
        ),
    )
    op.create_index(
        "ix_transactions_family_date_id_active",
        "transactions",
        [
            "family_budget_id",
            sa.text("transaction_date DESC"),
            sa.text("id DESC"),
        ],
        unique=False,
        postgresql_where=sa.text("is_deleted = false"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_transactions_family_date_id_active",
        table_name="transactions",
    )
    op.drop_index(
        "ix_transactions_expense_category_id_active",
        table_name="transactions",
    )
    op.drop_index(
        "ix_transactions_income_category_id_active",
        table_name="transactions",
    )
    op.drop_index(
        "ix_transactions_to_wallet_id_active",
        table_name="transactions",
    )
    op.drop_index(
        "ix_transactions_wallet_id_active",
        table_name="transactions",
    )
