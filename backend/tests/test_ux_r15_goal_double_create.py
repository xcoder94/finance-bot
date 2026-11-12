"""r15: two simultaneous POST /goals on one wallet: one 201, the other 409 (never 500)."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.goal import Goal
from tests.auth_helpers import bearer_header_for_telegram_id
from tests.test_ux_r13_goal_flag import _Env, _seed, real_engine  # noqa: F401
from tests.test_wallets_categories import _db_available

pytestmark = pytest.mark.skipif(not _db_available(), reason="postgres not available")


@pytest.mark.anyio
@pytest.mark.parametrize("copies", [2, 4])
async def test_parallel_goal_creation_one_201_rest_409(real_engine, copies):  # noqa: F811
    factory = async_sessionmaker(real_engine, expire_on_commit=False)
    tid, wids, _exp, _inc = await _seed(factory, 1, 0)
    wallet = wids[0]
    headers = bearer_header_for_telegram_id(tid)
    async with _Env(factory) as env:
        for rnd in range(25):
            async with factory() as s:
                await s.execute(delete(Goal).where(Goal.wallet_id == wallet))
                await s.commit()
            rs = await asyncio.gather(*[
                env.client.post(
                    "/api/v1/goals",
                    headers=headers,
                    json={"wallet_id": str(wallet), "target_amount": 999999, "name": "dup"},
                )
                for _ in range(copies)
            ])
            codes = sorted(r.status_code for r in rs)
            assert codes == [201] + [409] * (copies - 1), (rnd, codes, [r.text[:80] for r in rs])
            for r in rs:
                if r.status_code == 409:
                    assert r.json()["detail"] == "goal_already_exists"
            async with factory() as s:
                active = (
                    await s.scalars(
                        select(Goal).where(Goal.wallet_id == wallet, Goal.status == "active")
                    )
                ).all()
                assert len(active) == 1
