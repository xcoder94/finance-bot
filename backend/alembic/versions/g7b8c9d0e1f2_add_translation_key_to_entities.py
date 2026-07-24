"""add translation_key to wallets and categories

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-23 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "g7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("wallets", sa.Column("translation_key", sa.String(), nullable=True))
    op.add_column("income_categories", sa.Column("translation_key", sa.String(), nullable=True))
    op.add_column("expense_categories", sa.Column("translation_key", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("expense_categories", "translation_key")
    op.drop_column("income_categories", "translation_key")
    op.drop_column("wallets", "translation_key")
