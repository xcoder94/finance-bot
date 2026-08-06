"""One-off: soft-delete seeded demo transactions across all family budgets.

Customer-fired only. Never imported by bot startup, scheduler, or migrations.

Run from backend/:
    python scripts/clear_seeded_demo_transactions.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from urllib.parse import urlparse

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sqlalchemy import distinct, select

from app.config import DATABASE_URL
from app.db import async_session_factory, dispose_engine
from app.models.transaction import Transaction
from app.services.demo_data import clear_demo_transactions

_LOCAL_DB_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def database_host() -> str:
    parsed = urlparse(DATABASE_URL)
    host = parsed.hostname
    if not host:
        raise SystemExit("DATABASE_URL has no host; refusing to run")
    return host


def assert_local_database() -> str:
    host = database_host()
    if host not in _LOCAL_DB_HOSTS:
        print(f"blocked: database host is {host!r} (not local/dev)", file=sys.stderr)
        raise SystemExit(1)
    return host


async def run() -> tuple[int, int]:
    try:
        async with async_session_factory() as session:
            budget_ids = (
                await session.scalars(
                    select(distinct(Transaction.family_budget_id)).where(
                        Transaction.is_demo.is_(True),
                        Transaction.is_deleted.is_(False),
                    )
                )
            ).all()

            total_cleared = 0
            for budget_id in budget_ids:
                total_cleared += await clear_demo_transactions(session, budget_id)

            await session.commit()
            return total_cleared, len(budget_ids)
    finally:
        await dispose_engine()


def main() -> None:
    host = assert_local_database()
    total_cleared, budgets_affected = asyncio.run(run())
    print(f"database host: {host}")
    print(f"transactions cleared: {total_cleared}")
    print(f"family budgets affected: {budgets_affected}")


if __name__ == "__main__":
    main()
