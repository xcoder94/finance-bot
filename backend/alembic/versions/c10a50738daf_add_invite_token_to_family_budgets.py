"""add invite_token to family_budgets

Revision ID: c10a50738daf
Revises: 96192ca13fd1
Create Date: 2026-07-15 10:39:20.893356

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c10a50738daf'
down_revision: Union[str, Sequence[str], None] = '96192ca13fd1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("family_budgets", sa.Column("invite_token", sa.String(), nullable=True))
    op.create_index(
        op.f("ix_family_budgets_invite_token"),
        "family_budgets",
        ["invite_token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_family_budgets_invite_token"), table_name="family_budgets")
    op.drop_column("family_budgets", "invite_token")
