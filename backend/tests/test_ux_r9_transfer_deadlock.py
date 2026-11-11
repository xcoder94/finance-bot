"""Opposite parallel transfers between wallets with active goals must not deadlock (ux-r9).

Real concurrent connections (each request gets its own session from its own engine), data is
committed, as in production. The two requests lock the goal rows of the same two wallets;
before the fix they could take them in opposite order and one got a 500 after the transfer
row was already saved.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import DATABASE_URL
from app.db import get_session
from app.main import app
from app.models.family_budget import FamilyBudget
from app.models.goal import Goal
from app.models.ownership_transfer import OwnershipTransfer
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from tests.auth_helpers import TEST_APP_PASS_SECRET, bearer_header_for_telegram_id
from tests.test_wallets_categories import _db_available

pytestmark = pytest.mark.skipif(not _db_available(), reason="postgres not available")


def _opposite_set_order() -> tuple[uuid.UUID, uuid.UUID]:
    """Two ids whose Python set iterates in different orders depending on insertion."""
    while True:
        a, b = uuid.uuid4(), uuid.uuid4()
        if list({a, b}) != list({b, a}):
            return a, b


_SEEDED_TIDS: list[int] = []


async def _purge(engine) -> None:
    """Committed test data must not leak into tests that assume an empty database."""
    from sqlalchemy import delete

    from app.models.base import Base

    async with engine.begin() as conn:
        rows = (await conn.execute(
            select(User.id, User.family_budget_id).where(User.telegram_id.in_(_SEEDED_TIDS))
        )).all()
        user_ids = {r[0] for r in rows}
        budget_ids = {r[1] for r in rows}
        budget_ids |= set((await conn.execute(select(FamilyBudget.id).where(
            FamilyBudget.invite_token.like("dl-%") | FamilyBudget.invite_token.like("rb-%")
        ))).scalars())
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


async def _seed(factory, wallet_ids, targets) -> tuple[int, uuid.UUID]:
    tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    _SEEDED_TIDS.append(tid)
    async with factory() as s:
        budget = FamilyBudget(invite_token=f"dl-{uuid.uuid4()}")
        s.add(budget)
        await s.flush()
        s.add(User(telegram_id=tid, family_budget_id=budget.id, role="owner", language="ru"))
        for wid, target in zip(wallet_ids, targets, strict=True):
            s.add(Wallet(id=wid, family_budget_id=budget.id, name=f"W{str(wid)[:4]}",
                         currency="UZS", is_personal=False))
        await s.flush()
        for wid, target in zip(wallet_ids, targets, strict=True):
            s.add(Transaction(
                family_budget_id=budget.id, type="income", wallet_id=wid, amount=10_000_000,
                created_by_user_id=(await s.scalar(select(User.id).where(User.telegram_id == tid))),
                transaction_date=date.today(), channel="app",
            ))
            s.add(Goal(family_budget_id=budget.id, wallet_id=wid, name="DL",
                       target_amount=target, currency="UZS", status="active", crossed=False))
        await s.commit()
        return tid, budget.id


@pytest.mark.anyio
async def test_opposite_parallel_transfers_never_500(real_engine):
    factory = async_sessionmaker(real_engine, expire_on_commit=False)
    a, b = _opposite_set_order()
    tid, budget_id = await _seed(factory, [a, b], [999_999_999, 999_999_999])

    async def per_request_session() -> AsyncIterator[AsyncSession]:
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = per_request_session
    rounds = 20
    try:
        with patch("app.main.verify_postgres_connection", new=AsyncMock()), patch(
            "app.auth.deps.APP_PASS_SECRET", TEST_APP_PASS_SECRET
        ):
            headers = bearer_header_for_telegram_id(tid)
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                statuses: list[int] = []
                for _ in range(rounds):
                    body = {"amount": 1000, "transaction_date": date.today().isoformat()}
                    rs = await asyncio.gather(
                        c.post("/api/v1/transactions/transfer", headers=headers,
                               json={**body, "wallet_id": str(a), "to_wallet_id": str(b)}),
                        c.post("/api/v1/transactions/transfer", headers=headers,
                               json={**body, "wallet_id": str(b), "to_wallet_id": str(a)}),
                    )
                    statuses += [r.status_code for r in rs]
    finally:
        app.dependency_overrides.pop(get_session, None)

    async with factory() as s:
        transfers = await s.scalar(
            select(func.count()).select_from(Transaction).where(
                Transaction.family_budget_id == budget_id, Transaction.type == "transfer"
            )
        )
    assert statuses == [201] * (2 * rounds), statuses
    assert transfers == 2 * rounds


# --- bugs 2 and 3: parallel duplicates of membership operations -------------------------

async def _seed_family(factory, members: int):
    """Committed family: owner + `members` members. Returns (budget_id, owner_tid, [(tid, id)])."""
    base = int(uuid.uuid4().int % 8_000_000_000) + 1_000_000_000
    _SEEDED_TIDS.extend(range(base, base + members + 1))
    async with factory() as s:
        budget = FamilyBudget(invite_token=f"rb-{uuid.uuid4()}")
        s.add(budget)
        await s.flush()
        owner = User(telegram_id=base, family_budget_id=budget.id, role="owner", language="ru")
        s.add(owner)
        ms = []
        for i in range(members):
            u = User(telegram_id=base + 1 + i, family_budget_id=budget.id, role="member",
                     language="ru")
            s.add(u)
            ms.append(u)
        await s.commit()
        return budget.id, base, [(u.telegram_id, u.id) for u in ms]


class _Env:
    def __init__(self, factory):
        self.factory = factory
        self.sent: list[int] = []

    async def __aenter__(self):
        from app.services import goal_notify

        async def per_request_session():
            async with self.factory() as s:
                yield s

        sent = self.sent

        class FakeBot:
            async def send_message(self, chat_id, text, **kw):
                sent.append(chat_id)

            class session:  # noqa: N801
                @staticmethod
                async def close():
                    return None

        async def fake_resolve_bot(b):
            return FakeBot(), False

        app.dependency_overrides[get_session] = per_request_session
        self._patches = [
            patch("app.main.verify_postgres_connection", new=AsyncMock()),
            patch("app.auth.deps.APP_PASS_SECRET", TEST_APP_PASS_SECRET),
            patch("app.services.goal_notify.resolve_bot", fake_resolve_bot),
        ]
        for p in self._patches:
            p.start()
        self.goal_notify = goal_notify
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        return self

    async def __aexit__(self, *exc):
        await self.client.aclose()
        for p in self._patches:
            p.stop()
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.anyio
async def test_parallel_ownership_requests_to_one_member_never_500(real_engine):
    factory = async_sessionmaker(real_engine, expire_on_commit=False)
    _, owner_tid, members = await _seed_family(factory, 1)
    async with _Env(factory) as env:
        h = bearer_header_for_telegram_id(owner_tid)
        rs = await asyncio.gather(
            *[env.client.post(f"/api/v1/members/{members[0][1]}/transfer", headers=h)
              for _ in range(3)]
        )
        await env.goal_notify.drain_background()
    statuses = sorted(r.status_code for r in rs)
    assert all(s < 500 for s in statuses), statuses
    assert statuses.count(200) >= 1, statuses
    assert all(s == 409 for s in statuses if s != 200), statuses
    # every 200 is a real offer (an earlier one may have been replaced), every 409 sent nothing
    assert len(env.sent) == statuses.count(200), (statuses, env.sent)
    async with factory() as s:
        pending = await s.scalar(
            select(func.count()).select_from(OwnershipTransfer).where(
                OwnershipTransfer.to_user_id == members[0][1],
                OwnershipTransfer.status == "pending",
            )
        )
    assert pending == 1


@pytest.mark.anyio
async def test_parallel_leave_and_remove_notify_member_once(real_engine):
    factory = async_sessionmaker(real_engine, expire_on_commit=False)
    budget_id, owner_tid, members = await _seed_family(factory, 2)
    (mtid, mid), _ = members
    async with _Env(factory) as env:
        hm = bearer_header_for_telegram_id(mtid)
        ho = bearer_header_for_telegram_id(owner_tid)
        rs = await asyncio.gather(
            env.client.post("/api/v1/members/leave", headers=hm),
            env.client.post("/api/v1/members/leave", headers=hm),
            env.client.delete(f"/api/v1/members/{mid}", headers=ho),
        )
        await env.goal_notify.drain_background()
    statuses = [r.status_code for r in rs]
    assert all(s < 500 for s in statuses), statuses
    assert sum(1 for s in statuses if s == 200) == 1, statuses
    assert env.sent == [mtid], env.sent  # exactly one notice to the member
    async with factory() as s:
        budgets_of_member = await s.scalar(
            select(func.count()).select_from(FamilyBudget).join(
                User, User.family_budget_id == FamilyBudget.id
            ).where(User.telegram_id == mtid)
        )
    assert budgets_of_member == 1

