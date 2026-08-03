"""phase1 quick entry schema

Revision ID: i9d0e1f2a3b4
Revises: h8c9d0e1f2a3
Create Date: 2026-08-03 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "i9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "h8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "wallets",
        sa.Column("is_personal", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "wallets",
        sa.Column("owner_user_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_wallets_owner_user_id_users",
        "wallets",
        "users",
        ["owner_user_id"],
        ["id"],
    )
    op.add_column(
        "users",
        sa.Column("default_wallet_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_default_wallet_id_wallets",
        "users",
        "wallets",
        ["default_wallet_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "family_budgets",
        sa.Column("daily_model_calls", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "family_budgets",
        sa.Column("daily_unparsed", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "family_budgets",
        sa.Column("counters_day", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("family_budgets", "counters_day")
    op.drop_column("family_budgets", "daily_unparsed")
    op.drop_column("family_budgets", "daily_model_calls")
    op.drop_constraint("fk_users_default_wallet_id_wallets", "users", type_="foreignkey")
    op.drop_column("users", "default_wallet_id")
    op.drop_constraint("fk_wallets_owner_user_id_users", "wallets", type_="foreignkey")
    op.drop_column("wallets", "owner_user_id")
    op.drop_column("wallets", "is_personal")
