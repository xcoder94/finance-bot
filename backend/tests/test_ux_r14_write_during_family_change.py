"""A write that starts while its author is joining / leaving a family must not land in the old budget (ux-r14).

Real parallel connections, committed data. The membership change is held open (locks taken,
not yet committed) while the write request runs, then committed: exactly the interleaving QA
saw (history -3 003, wallet -18 006: rows kept in the deleted budget).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import DATABASE_URL
from app.db import get_session
from app.main import app
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.goal import Goal
from app.models.income_category import IncomeCategory
from app.models.ownership_transfer import OwnershipTransfer
from app.models.shopping import ShoppingItem
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.membership_lifecycle import (
    convert_join_with_own_budget,
    detach_member_to_own_budget,
    lock_for_join,
)
from tests.auth_helpers import TEST_APP_PASS_SECRET, bearer_header_for_telegram_id
from tests.test_wallets_categories import _db_available

pytestmark = pytest.mark.skipif(not _db_available(), reason="postgres not available")

_TIDS: list[int] = []
MARK = "RACEMARK"
HOLD = 0.8


async def _purge(engine) -> None:
    from app.models.base import Base

    async with engine.begin() as conn:
        rows = (await conn.execute(
            select(User.id, User.family_budget_id).where(User.telegram_id.in_(_TIDS))
        )).all()
        user_ids = {r[0] for r in rows}
        budget_ids = {r[1] for r in rows}
        budget_ids |= set((await conn.execute(
            select(FamilyBudget.id).where(FamilyBudget.invite_token.like("rc-%"))
        )).scalars())
        await conn.execute(delete(OwnershipTransfer).where(
            OwnershipTransfer.family_budget_id.in_(budget_ids)))
        for table in reversed(Base.metadata.sorted_tables):
            if table.name in ("family_budgets", "users", "alembic_version"):
                continue
            if "family_budget_id" in table.c:
                await conn.execute(delete(table).where(table.c.family_budget_id.in_(budget_ids)))
        await conn.execute(delete(User).where(User.family_budget_id.in_(budget_ids)))
        await conn.execute(delete(User).where(User.id.in_(user_ids)))
        await conn.execute(delete(FamilyBudget).where(FamilyBudget.id.in_(budget_ids)))


@pytest.fixture
async def real_engine() -> AsyncIterator:
    eng = create_async_engine(DATABASE_URL, pool_size=10)
    yield eng
    await _purge(eng)
    await eng.dispose()


def _tid() -> int:
    tid = int(uuid.uuid4().int % 8_000_000_000) + 1_000_000_000
    _TIDS.append(tid)
    return tid


class World:
    """me (owner of a solo budget, or member of a family) + the budget he will join/leave."""

    def __init__(self, factory):
        self.factory = factory

    async def seed(self, *, as_member: bool) -> World:
        self.tid, self.other_tid = _tid(), _tid()
        async with self.factory() as s:
            old = FamilyBudget(invite_token=f"rc-{uuid.uuid4()}")
            target = FamilyBudget(invite_token=f"rc-{uuid.uuid4()}")
            s.add_all([old, target])
            await s.flush()
            other = User(telegram_id=self.other_tid, family_budget_id=(old if as_member else target).id,
                         role="owner", language="ru")
            me = User(telegram_id=self.tid, family_budget_id=old.id,
                      role="member" if as_member else "owner", language="ru")
            s.add_all([other, me])
            await s.flush()
            self.old_id, self.target_id, self.me_id = old.id, target.id, me.id
            self.p1, self.p2, self.shared = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            s.add_all([
                Wallet(id=self.p1, family_budget_id=old.id, name="P1", currency="UZS",
                       is_personal=True, owner_user_id=me.id),
                Wallet(id=self.p2, family_budget_id=old.id, name="P2", currency="UZS",
                       is_personal=True, owner_user_id=me.id),
                Wallet(id=self.shared, family_budget_id=old.id, name="S", currency="UZS",
                       is_personal=False),
            ])
            ec = ExpenseCategory(family_budget_id=old.id, name="Food")
            ic = IncomeCategory(family_budget_id=old.id, name="Salary")
            s.add_all([ec, ic])
            await s.flush()
            self.ec, self.ic = ec.id, ic.id
            s.add(Transaction(family_budget_id=old.id, type="income", wallet_id=self.p1,
                              amount=1_000_000, income_category_id=ic.id, created_by_user_id=me.id,
                              transaction_date=date.today(), channel="app"))
            await s.commit()
        self.headers = bearer_header_for_telegram_id(self.tid)
        return self

    async def change_family(self, kind: str, started: asyncio.Event) -> None:
        """Join / leave with its locks held for HOLD seconds before commit."""
        async with self.factory() as s:
            me = await s.scalar(select(User).where(User.telegram_id == self.tid))
            if kind == "join":
                target = await s.get(FamilyBudget, self.target_id)
                assert await lock_for_join(s, user=me, target=target)
                await convert_join_with_own_budget(s, user=me, target=target)
            else:
                old = await s.get(FamilyBudget, self.old_id)
                await detach_member_to_own_budget(
                    s, departing_user=me, old_budget=old, reason="left", bot=None
                )
            started.set()
            await asyncio.sleep(HOLD)
            await s.commit()


def _body(kind: str, w: World) -> tuple[str, str, dict]:
    d = date.today().isoformat()
    if kind == "expense":
        return "post", "/api/v1/transactions/expense", {
            "wallet_id": str(w.p1), "amount": 3003, "expense_category_id": str(w.ec),
            "transaction_date": d}
    if kind == "income":
        return "post", "/api/v1/transactions/income", {
            "wallet_id": str(w.p1), "amount": 3003, "income_category_id": str(w.ic),
            "transaction_date": d}
    if kind == "transfer":
        return "post", "/api/v1/transactions/transfer", {
            "wallet_id": str(w.p1), "to_wallet_id": str(w.p2), "amount": 3003,
            "transaction_date": d}
    if kind == "wallet":
        return "post", "/api/v1/wallets", {"name": MARK, "currency": "UZS", "is_personal": True}
    if kind == "category":
        return "post", "/api/v1/categories/expense", {"name": MARK}
    if kind == "goal":
        return "post", "/api/v1/goals", {"wallet_id": str(w.shared), "target_amount": 500_000}
    if kind == "shopping":
        return "post", "/api/v1/shopping/items", {"name": MARK}
    raise AssertionError(kind)


async def _run(real_engine, change: str, write: str):
    factory = async_sessionmaker(real_engine, expire_on_commit=False)
    w = await World(factory).seed(as_member=(change == "leave"))

    async def per_request_session() -> AsyncIterator[AsyncSession]:
        async with factory() as s:
            yield s

    from unittest.mock import AsyncMock, patch

    app.dependency_overrides[get_session] = per_request_session
    started = asyncio.Event()
    try:
        with patch("app.main.verify_postgres_connection", new=AsyncMock()), patch(
            "app.auth.deps.APP_PASS_SECRET", TEST_APP_PASS_SECRET
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                changer = asyncio.create_task(w.change_family(change, started))
                await started.wait()
                method, path, body = _body(write, w)
                resp = await getattr(c, method)(path, headers=w.headers, json=body)
                await changer
    finally:
        app.dependency_overrides.pop(get_session, None)
    return factory, w, resp


async def _stranded(factory, w: World, change: str, write: str) -> list[str]:
    """What a person would see wrong afterwards: rows of his in the budget he is no longer in."""
    out: list[str] = []
    async with factory() as s:
        me = await s.get(User, w.me_id)
        await s.refresh(me)
        if change == "join":
            gone = w.old_id
            if (await s.get(FamilyBudget, gone)).is_deleted is not True:
                out.append("old budget not deleted")
            n = await s.scalar(select(func.count()).select_from(Transaction).where(
                Transaction.family_budget_id == gone, Transaction.is_deleted.is_(False)))
            if n:
                out.append(f"{n} live transaction(s) in the deleted budget")
            n = await s.scalar(select(func.count()).select_from(Wallet).where(
                Wallet.family_budget_id == gone, Wallet.is_deleted.is_(False)))
            if n:
                out.append(f"{n} live wallet(s) in the deleted budget")
            n = await s.scalar(select(func.count()).select_from(Goal).where(
                Goal.family_budget_id == gone))
            if n:
                out.append(f"{n} goal(s) in the deleted budget")
            n = await s.scalar(select(func.count()).select_from(ShoppingItem).where(
                ShoppingItem.family_budget_id == gone, ShoppingItem.name == MARK))
            if n:
                out.append(f"{n} shopping item(s) in the deleted budget")
            n = await s.scalar(select(func.count()).select_from(ExpenseCategory).where(
                ExpenseCategory.family_budget_id == gone, ExpenseCategory.name == MARK))
            if n:
                out.append(f"{n} category(ies) created in the deleted budget")
        else:
            # he left: his personal wallets and everything on them must be in his new budget
            n = await s.scalar(select(func.count()).select_from(Wallet).where(
                Wallet.owner_user_id == w.me_id, Wallet.is_deleted.is_(False),
                Wallet.family_budget_id != me.family_budget_id))
            if n:
                out.append(f"{n} personal wallet(s) of his left in the old family")
            rows = (await s.execute(
                select(Transaction.id).join(Wallet, Wallet.id == Transaction.wallet_id).where(
                    Wallet.owner_user_id == w.me_id, Transaction.is_deleted.is_(False),
                    Transaction.family_budget_id != Wallet.family_budget_id))).all()
            if rows:
                out.append(f"{len(rows)} transaction(s) kept in the old family on his wallet")
        # money: wallet balance movement == sum of live operations visible in his budget
        for wid in (w.p1, w.p2):
            in_budget = await s.scalar(select(func.count()).select_from(Transaction).where(
                (Transaction.wallet_id == wid) | (Transaction.to_wallet_id == wid),
                Transaction.is_deleted.is_(False),
                Transaction.family_budget_id != me.family_budget_id))
            if in_budget:
                out.append(f"{in_budget} operation(s) on wallet {wid} outside his current budget")
    return out


JOIN_WRITES = ["expense", "income", "transfer", "wallet", "category", "goal", "shopping"]
LEAVE_WRITES = ["expense", "income", "transfer", "wallet"]


@pytest.mark.anyio
@pytest.mark.parametrize("write", JOIN_WRITES)
async def test_write_during_join_never_lands_in_deleted_budget(real_engine, write):
    factory, w, resp = await _run(real_engine, "join", write)
    assert resp.status_code in (201, 409), (resp.status_code, resp.text)
    assert await _stranded(factory, w, "join", write) == []
    if resp.status_code == 409:
        assert resp.json()["detail"] == "family_changed"


@pytest.mark.anyio
@pytest.mark.parametrize("write", LEAVE_WRITES)
async def test_write_during_leave_never_lands_in_old_family(real_engine, write):
    factory, w, resp = await _run(real_engine, "leave", write)
    assert resp.status_code in (201, 409), (resp.status_code, resp.text)
    assert await _stranded(factory, w, "leave", write) == []
    if resp.status_code == 409:
        assert resp.json()["detail"] == "family_changed"


@pytest.mark.anyio
async def test_blocked_write_is_refused_not_lost_and_retry_works(real_engine):
    """The refused request saves nothing; the same request repeated after the join succeeds."""
    factory, w, resp = await _run(real_engine, "join", "wallet")
    assert resp.status_code == 409 and resp.json()["detail"] == "family_changed"
    async with factory() as s:
        assert await s.scalar(select(func.count()).select_from(Wallet).where(Wallet.name == MARK)) == 0

    async def per_request_session() -> AsyncIterator[AsyncSession]:
        async with factory() as s:
            yield s

    from unittest.mock import AsyncMock, patch

    app.dependency_overrides[get_session] = per_request_session
    try:
        with patch("app.main.verify_postgres_connection", new=AsyncMock()), patch(
            "app.auth.deps.APP_PASS_SECRET", TEST_APP_PASS_SECRET
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                again = await c.post("/api/v1/wallets", headers=w.headers,
                                     json={"name": MARK, "currency": "UZS", "is_personal": True})
    finally:
        app.dependency_overrides.pop(get_session, None)
    assert again.status_code == 201
    async with factory() as s:
        wl = await s.scalar(select(Wallet).where(Wallet.name == MARK))
        assert wl.family_budget_id == w.target_id


# --- bot / service paths (no HTTP layer): same guard ---------------------------------------

@pytest.mark.anyio
@pytest.mark.parametrize("write", ["quick_expense", "quick_income", "quick_transfer", "shopping_add"])
async def test_bot_write_during_join_never_lands_in_deleted_budget(real_engine, write):
    from datetime import UTC, datetime

    from app.services.family_guard import FamilyChangedError
    from app.services.quick_entry_create import (
        create_quick_entry_expense,
        create_quick_entry_income,
    )
    from app.services.quick_entry_transfer import create_quick_entry_transfer
    from app.services.shopping import add_shopping_items

    factory = async_sessionmaker(real_engine, expire_on_commit=False)
    w = await World(factory).seed(as_member=False)
    started = asyncio.Event()
    changer = asyncio.create_task(w.change_family("join", started))
    await started.wait()
    refused = False
    async with factory() as s:
        me = await s.scalar(select(User).where(User.telegram_id == w.tid))  # old budget in memory
        now = datetime.now(UTC)
        try:
            if write == "quick_expense":
                await create_quick_entry_expense(
                    s, me, amount=3003, wallet_id=w.p1, expense_category_id=w.ec, comment=None,
                    transaction_date=now, channel="text")
            elif write == "quick_income":
                await create_quick_entry_income(
                    s, me, amount=3003, wallet_id=w.p1, income_category_id=w.ic, comment=None,
                    transaction_date=now, channel="text")
            elif write == "quick_transfer":
                await create_quick_entry_transfer(
                    s, me, from_wallet_id=w.p1, to_wallet_id=w.p2, amount=3003, rate=None,
                    comment=None, transaction_date=now, channel="text")
            else:
                await add_shopping_items(s, me, [MARK])
        except FamilyChangedError:
            refused = True
    await changer
    assert refused or await _stranded(factory, w, "join", write) == []
    assert await _stranded(factory, w, "join", write) == []
