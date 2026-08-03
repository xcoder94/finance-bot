import pytest
from sqlalchemy import inspect

from app.db import engine


async def _reset_engine() -> None:
    await engine.dispose()


@pytest.mark.anyio
async def test_family_budget_name_column_exists():
    await _reset_engine()
    async with engine.connect() as conn:
        def check(sync_conn):
            insp = inspect(sync_conn)
            columns = {c["name"] for c in insp.get_columns("family_budgets")}
            assert "name" in columns

        await conn.run_sync(check)
