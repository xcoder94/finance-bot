"""support_messages table

Revision ID: u1d2e3f4a5b6
Revises: t0c1d2e3f4a5
Create Date: 2026-08-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "u1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "t0c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "support_messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("forwarded_message_id", sa.Integer(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("family_budget_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["family_budget_id"], ["family_budgets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_support_messages_forwarded_message_id"),
        "support_messages",
        ["forwarded_message_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_support_messages_forwarded_message_id"),
        table_name="support_messages",
    )
    op.drop_table("support_messages")
