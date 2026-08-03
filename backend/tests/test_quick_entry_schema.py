import pytest
from sqlalchemy import inspect
from app.db import engine


async def _reset_engine() -> None:
    await engine.dispose()


@pytest.mark.anyio
async def test_phase1_columns_exist():
    await _reset_engine()
    async with engine.connect() as conn:
        def check(sync_conn):
            insp = inspect(sync_conn)
            w = {c["name"] for c in insp.get_columns("wallets")}
            u = {c["name"] for c in insp.get_columns("users")}
            f = {c["name"] for c in insp.get_columns("family_budgets")}
            assert {"is_personal", "owner_user_id"} <= w
            assert "default_wallet_id" in u
            assert {"daily_model_calls", "daily_unparsed", "counters_day"} <= f
        await conn.run_sync(check)
