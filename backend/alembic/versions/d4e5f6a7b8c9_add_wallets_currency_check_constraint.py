"""add wallets currency check constraint

Revision ID: d4e5f6a7b8c9
Revises: c10a50738daf
Create Date: 2026-07-15 12:40:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c10a50738daf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_wallets_currency",
        "wallets",
        "currency IN ('UZS', 'USD')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_wallets_currency", "wallets", type_="check")
