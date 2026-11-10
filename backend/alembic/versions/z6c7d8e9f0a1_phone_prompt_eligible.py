"""Deferred phone request (PRD-ux U7): users.phone_prompt_eligible_at

Revision ID: z6c7d8e9f0a1
Revises: y5b6c7d8e9f0
Create Date: 2026-11-10 12:00:00.000000

Contract: work/db/ux-p6-delta.md. Expand-only. Nullable column without a default and
without a backfill -> catalog-only change (no table rewrite, no existing row is written).
NULL means "already handled" for every existing user, so none of them is ever asked by the
deferred path.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "z6c7d8e9f0a1"
down_revision: Union[str, None] = "y5b6c7d8e9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.add_column(
        "users",
        sa.Column("phone_prompt_eligible_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "phone_prompt_eligible_at")
