"""ux-r12: ownership races (security r2 M1, L1, L2). Real parallel connections, committed data.

Invariant after any race: every living family has exactly one living owner, and nobody lives in
a deleted family.
"""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.family_budget import FamilyBudget
from app.models.ownership_transfer import OwnershipTransfer
from app.models.user import User
from app.services import ownership_transfer as ot
from tests.auth_helpers import bearer_header_for_telegram_id
from tests.test_ux_r9_transfer_deadlock import (  # noqa: F401
    _Env,
    _seed_family,
    _SEEDED_TIDS,
    pytestmark,
    real_engine,
)

# Holds the accept transaction open (locks held) for a moment after it has read everything,
# so a concurrent leave/remove really lands in the middle of it.
ACCEPT_PAUSE = 0.4


@pytest.fixture
def slow_accept(monkeypatch):
    original = AsyncSession.scalars

    async def scalars(self, statement, *a, **k):
        if "users.id NOT IN" in str(statement):  # the last read of accept_ownership_transfer
            await asyncio.sleep(ACCEPT_PAUSE)
        return await original(self, statement, *a, **k)

    monkeypatch.setattr(AsyncSession, "scalars", scalars)


async def _offer(factory, budget_id, owner_id, member_id) -> uuid.UUID:
    async with factory() as s:
        row = OwnershipTransfer(
            family_budget_id=budget_id, from_user_id=owner_id, to_user_id=member_id,
            status="pending",
        )
        s.add(row)
        await s.commit()
        return row.id


async def _accept(factory, member_tid, transfer_id) -> str:
    async with factory() as s:
        async with s.begin():
            user = await s.scalar(select(User).where(User.telegram_id == member_tid))
            try:
                await ot.accept_ownership_transfer(
                    s, transfer_id=transfer_id, actor=user, bot=None
                )
            except ot.TransferStaleError:
                return "stale"
            except ot.TransferNotPendingError:
                return "not_pending"
    return "accepted"


async def _assert_owner_invariant(factory, tids) -> None:
    async with factory() as s:
        users = (await s.scalars(select(User).where(User.telegram_id.in_(tids)))).all()
        budgets = {
            b.id: b
            for b in (
                await s.scalars(
                    select(FamilyBudget).where(
                        FamilyBudget.id.in_({u.family_budget_id for u in users})
                    )
                )
            ).all()
        }
        for u in users:
            assert not budgets[u.family_budget_id].is_deleted, f"{u.telegram_id} lives in a deleted family"
        for bid, b in budgets.items():
            if b.is_deleted:
                continue
            owners = [u for u in users if u.family_budget_id == bid and u.role == "owner"
                      and not u.is_deleted]
            assert len(owners) == 1, f"family {bid} has {len(owners)} owners"


@pytest.mark.anyio
@pytest.mark.parametrize("how", ["leave", "remove"])
async def test_accept_racing_with_leave_or_remove_keeps_one_owner(real_engine, slow_accept, how):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = async_sessionmaker(real_engine, expire_on_commit=False)
    budget_id, owner_tid, members = await _seed_family(factory, 1)
    (mtid, mid) = members[0]
    async with factory() as s:
        owner_id = await s.scalar(select(User.id).where(User.telegram_id == owner_tid))
    transfer_id = await _offer(factory, budget_id, owner_id, mid)
    async with _Env(factory) as env:
        async def act():
            await asyncio.sleep(0.15)  # accept is already holding its transaction
            if how == "leave":
                return await env.client.post(
                    "/api/v1/members/leave", headers=bearer_header_for_telegram_id(mtid))
            return await env.client.delete(
                f"/api/v1/members/{mid}", headers=bearer_header_for_telegram_id(owner_tid))

        accepted, resp = await asyncio.gather(_accept(factory, mtid, transfer_id), act())
        await env.goal_notify.drain_background()
    assert resp.status_code < 500, (accepted, resp.status_code, resp.text)
    await _assert_owner_invariant(factory, [owner_tid, mtid])


@pytest.mark.anyio
async def test_remove_of_member_who_just_became_owner_is_409_not_500(real_engine):
    factory = async_sessionmaker(real_engine, expire_on_commit=False)
    statuses = []
    for _ in range(12):
        budget_id, owner_tid, members = await _seed_family(factory, 1)
        (mtid, mid) = members[0]
        async with factory() as s:
            owner_id = await s.scalar(select(User.id).where(User.telegram_id == owner_tid))
        transfer_id = await _offer(factory, budget_id, owner_id, mid)
        async with _Env(factory) as env:
            _, resp = await asyncio.gather(
                _accept(factory, mtid, transfer_id),
                env.client.delete(
                    f"/api/v1/members/{mid}", headers=bearer_header_for_telegram_id(owner_tid)),
            )
            await env.goal_notify.drain_background()
        statuses.append(resp.status_code)
        await _assert_owner_invariant(factory, [owner_tid, mtid])
    assert 500 not in statuses, statuses


@pytest.mark.anyio
async def test_refuse_after_accept_does_not_overwrite_accepted(real_engine, slow_accept):
    factory = async_sessionmaker(real_engine, expire_on_commit=False)
    budget_id, owner_tid, members = await _seed_family(factory, 1)
    (mtid, mid) = members[0]
    async with factory() as s:
        owner_id = await s.scalar(select(User.id).where(User.telegram_id == owner_tid))
    transfer_id = await _offer(factory, budget_id, owner_id, mid)

    async def refuse():
        await asyncio.sleep(0.15)
        async with factory() as s:
            async with s.begin():
                user = await s.scalar(select(User).where(User.telegram_id == mtid))
                try:
                    await ot.refuse_ownership_transfer(
                        s, transfer_id=transfer_id, actor=user, bot=None)
                except (ot.TransferNotFoundError, ot.TransferNotPendingError):
                    return "late"
        return "refused"

    with patch("app.services.goal_notify.resolve_bot", AsyncMock(return_value=(AsyncMock(), False))):
        accepted, refused = await asyncio.gather(_accept(factory, mtid, transfer_id), refuse())
    async with factory() as s:
        status = await s.scalar(
            select(OwnershipTransfer.status).where(OwnershipTransfer.id == transfer_id))
        owner_role = await s.scalar(select(User.role).where(User.telegram_id == mtid))
    # the stored decision matches what really happened to the roles
    assert (status == "accepted") == (owner_role == "owner"), (accepted, refused, status, owner_role)
    await _assert_owner_invariant(factory, [owner_tid, mtid])


# ------------------------------------------------------------------ L2: join chain

async def _solo(factory, tag):
    base = int(uuid.uuid4().int % 8_000_000_000) + 1_000_000_000
    _SEEDED_TIDS.append(base)
    async with factory() as s:
        budget = FamilyBudget(invite_token=f"rb-{tag}-{uuid.uuid4()}")
        s.add(budget)
        await s.flush()
        s.add(User(telegram_id=base, family_budget_id=budget.id, role="owner", language="ru"))
        await s.commit()
        return base, budget.invite_token


def _callback(tid, token):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=tid),
        data=f"join_accept:{token}",
        message=SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock(), delete=AsyncMock()),
        answer=AsyncMock(),
    )


@pytest.mark.anyio
@pytest.mark.parametrize("head_start", ["b", "c", "none"])
async def test_join_chain_never_leaves_someone_in_a_deleted_family(real_engine, head_start):
    """B joins F while C joins B's own family P at the same moment."""
    from bot import membership

    factory = async_sessionmaker(real_engine, expire_on_commit=False)
    a_tid, f_token = await _solo(factory, "f")
    b_tid, p_token = await _solo(factory, "p")
    c_tid, _ = await _solo(factory, "c")
    original = membership.evaluate_join_from_own_budget

    async def slow_evaluate(*a, **k):
        result = await original(*a, **k)
        await asyncio.sleep(0.3)  # both are past their checks before either converts
        return result

    async def join(tid, token, delay):
        await asyncio.sleep(delay)
        await membership.join_accept(_callback(tid, token))

    with patch("bot.membership.async_session_factory", factory), patch(
        "bot.membership.evaluate_join_from_own_budget", slow_evaluate
    ):
        await asyncio.gather(
            join(b_tid, f_token, 0.1 if head_start == "c" else 0),
            join(c_tid, p_token, 0.1 if head_start == "b" else 0),
        )
    await _assert_owner_invariant(factory, [a_tid, b_tid, c_tid])
