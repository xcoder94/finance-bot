"""expense_categories_parent_id_nullable

Revision ID: 96192ca13fd1
Revises: a1b2c3d4e5f6
Create Date: 2026-07-11 19:08:07.098084

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '96192ca13fd1'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "expense_categories",
        "parent_id",
        existing_type=sa.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "expense_categories",
        "parent_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
