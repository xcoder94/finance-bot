"""Category and subcategory caps must hold under concurrent creation.

`app/api/v1/categories.py` enforces every cap by counting rows and then
inserting. Without a lock on the parent budget row two concurrent requests
both read the same count and both insert: measured here, 10 concurrent
attempts at cap-1 let 6 through and pushed a cap of 8 to 13.
"""

from __future__ import annotations

import asyncio
import tempfile
import uuid

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.models.base import Base
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.services.entity_limits import PARENT_CATEGORY_LIMIT, lock_family_budget


# A file-backed sqlite database of its own, so writer locking is genuinely
# exercised across separate connections without borrowing the application
# engine — which the full-suite run has already bound to another event loop.
# Same pattern as tests/test_entity_caps_concurrency.py.
@pytest.fixture
async def engine():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        eng = create_async_engine(f"sqlite+aiosqlite:///{tmp.name}")

        @event.listens_for(eng.sync_engine, "connect")
        def _pragmas(dbapi_connection, _):  # pragma: no cover - sqlite plumbing
            dbapi_connection.execute("PRAGMA foreign_keys=ON")
            dbapi_connection.execute("PRAGMA busy_timeout=5000")

        async with eng.begin() as conn:
            await conn.run_sync(
                Base.metadata.create_all,
                tables=[FamilyBudget.__table__, ExpenseCategory.__table__],
            )

        yield eng
        await eng.dispose()


async def _seed_budget_at_cap_minus_one(engine) -> uuid.UUID:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        budget = FamilyBudget(name="cap-race")
        session.add(budget)
        await session.commit()
        await session.refresh(budget)
        for index in range(PARENT_CATEGORY_LIMIT - 1):
            session.add(
                ExpenseCategory(
                    family_budget_id=budget.id,
                    name=f"seed-{index}",
                    color_index=0,
                )
            )
        await session.commit()
        return budget.id


async def _count_parents(engine, budget_id: uuid.UUID) -> int:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        return await session.scalar(
            select(func.count())
            .select_from(ExpenseCategory)
            .where(
                ExpenseCategory.family_budget_id == budget_id,
                ExpenseCategory.parent_id.is_(None),
                ExpenseCategory.is_protected.is_(False),
            )
        )


async def _create_under_cap(engine, budget_id: uuid.UUID) -> bool:
    """The same count-then-insert shape the endpoint uses, with the lock."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        async with session.begin():
            await lock_family_budget(session, budget_id)
            current = await session.scalar(
                select(func.count())
                .select_from(ExpenseCategory)
                .where(
                    ExpenseCategory.family_budget_id == budget_id,
                    ExpenseCategory.is_deleted.is_(False),
                    ExpenseCategory.parent_id.is_(None),
                    ExpenseCategory.is_protected.is_(False),
                )
            )
            if current >= PARENT_CATEGORY_LIMIT:
                return False
            session.add(
                ExpenseCategory(
                    family_budget_id=budget_id,
                    name=f"race-{uuid.uuid4().hex[:8]}",
                    color_index=0,
                )
            )
            return True


@pytest.mark.anyio
async def test_concurrent_category_creates_never_exceed_the_cap(engine):
    budget_id = await _seed_budget_at_cap_minus_one(engine)

    results = await asyncio.gather(
        *[_create_under_cap(engine, budget_id) for _ in range(10)]
    )

    assert results.count(True) == 1, "exactly one attempt may take the last slot"
    assert await _count_parents(engine, budget_id) == PARENT_CATEGORY_LIMIT


@pytest.mark.anyio
async def test_endpoint_takes_the_budget_lock_before_counting():
    """The lock must be wired into the endpoints, not merely available.

    Reverting the `await lock_family_budget(...)` call while leaving the helper
    in place would keep every other test in this file green.
    """
    import inspect

    from app.api.v1 import categories

    for handler in (categories.create_income_category, categories.create_expense_category):
        source = inspect.getsource(handler)
        assert "lock_family_budget" in source, (
            f"{handler.__name__} must take the budget lock before counting"
        )
