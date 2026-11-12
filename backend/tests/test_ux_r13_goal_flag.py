"""Goal flag invariant under real parallel requests (ux-r13).

After all concurrent requests finish: goal.crossed == (balance >= target); a notice is sent
only on a real "below -> reached" transition (never twice for one transition); no 500.
Real separate connections, committed data (as in tests/test_ux_r9_transfer_deadlock.py).
"""

from __future__ import annotations

import asyncio
import random
import uuid
from collections.abc import AsyncIterator
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import DATABASE_URL
from app.db import get_session
from app.main import app
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.goal import Goal
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.quick_entry_balance import wallet_balance
from tests.auth_helpers import TEST_APP_PASS_SECRET, bearer_header_for_telegram_id
from tests.test_ux_r9_transfer_deadlock import _SEEDED_TIDS, _purge
from tests.test_wallets_categories import _db_available

pytestmark = pytest.mark.skipif(not _db_available(), reason="postgres not available")

TARGET = 10_000


@pytest.fixture
async def real_engine() -> AsyncIterator:
    eng = create_async_engine(DATABASE_URL, pool_size=10)
    yield eng
    await _purge(eng)
    await eng.dispose()


class _Env:
    def __init__(self, factory):
        self.factory = factory
        self.sent: list[int] = []

    async def __aenter__(self):
        from app.services import goal_notify

        async def per_request_session() -> AsyncIterator[AsyncSession]:
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


async def _seed(factory, n_wallets: int, start_balance: int):
    tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    _SEEDED_TIDS.append(tid)
    wallet_ids = [uuid.uuid4() for _ in range(n_wallets)]
    async with factory() as s:
        budget = FamilyBudget(invite_token=f"dl-{uuid.uuid4()}")
        s.add(budget)
        await s.flush()
        user = User(telegram_id=tid, family_budget_id=budget.id, role="owner", language="ru")
        s.add(user)
        exp = ExpenseCategory(family_budget_id=budget.id, name="E")
        inc = IncomeCategory(family_budget_id=budget.id, name="I")
        s.add_all([exp, inc])
        for wid in wallet_ids:
            s.add(Wallet(id=wid, family_budget_id=budget.id, name=f"W{str(wid)[:4]}",
                         currency="UZS", is_personal=False))
        await s.flush()
        for wid in wallet_ids:
            s.add(Transaction(
                family_budget_id=budget.id, type="income", wallet_id=wid, amount=start_balance,
                created_by_user_id=user.id, transaction_date=date.today(), channel="app",
            ))
            s.add(Goal(family_budget_id=budget.id, wallet_id=wid, name="G", target_amount=TARGET,
                       currency="UZS", status="active", crossed=start_balance >= TARGET))
        await s.commit()
        return tid, wallet_ids, exp.id, inc.id


async def _state(factory, wallet_ids):
    out = {}
    async with factory() as s:
        for wid in wallet_ids:
            goal = await s.scalar(select(Goal).where(Goal.wallet_id == wid))
            await s.refresh(goal)
            out[wid] = (goal.crossed, await wallet_balance(s, wid))
    return out


def _post(env, headers, kind, wallet, amount, exp, inc, to_wallet=None):
    body = {"amount": amount, "transaction_date": date.today().isoformat(),
            "wallet_id": str(wallet)}
    if kind == "income":
        body["income_category_id"] = str(inc)
    elif kind == "expense":
        body["expense_category_id"] = str(exp)
    else:
        body["to_wallet_id"] = str(to_wallet)
    return env.client.post(f"/api/v1/transactions/{kind}", headers=headers, json=body)


async def _run(real_engine, rounds, n_wallets, start, make_calls, seed=1, exact=None):
    """Each round: fire calls in parallel, then check the invariant and the notice count."""
    rnd = random.Random(seed)
    factory = async_sessionmaker(real_engine, expire_on_commit=False)
    tid, wids, exp, inc = await _seed(factory, n_wallets, start)
    headers = bearer_header_for_telegram_id(tid)
    problems: list[str] = []
    async with _Env(factory) as env:
        for i in range(rounds):
            before = await _state(factory, wids)
            env.sent.clear()
            calls_made = make_calls(env, headers, wids, exp, inc, rnd, before)
            rs = await asyncio.gather(*calls_made)
            await env.goal_notify.drain_background()
            after = await _state(factory, wids)
            if any(r.status_code >= 400 for r in rs):
                problems.append(f"round {i}: statuses {[r.status_code for r in rs]}")
            for wid in wids:
                crossed, bal = after[wid]
                if crossed != (bal >= TARGET):
                    problems.append(f"round {i}: flag {crossed} but balance {bal}/{TARGET}")
            reached = sum(1 for w in wids if after[w][0] and not before[w][0])
            if len(env.sent) < reached or len(env.sent) > len(calls_made):
                problems.append(f"round {i}: notices {len(env.sent)} for {reached} reached")
            if exact is not None and (exact(before, after) != len(env.sent)):
                problems.append(f"round {i}: notices {len(env.sent)}, expected {exact(before, after)}")
    assert not problems, problems[:5]


@pytest.mark.anyio
async def test_parallel_plus_and_minus_keep_flag_equal_to_balance(real_engine):
    def calls(env, h, wids, exp, inc, rnd, before):
        w = wids[0]
        # plus alone reaches the goal, minus alone leaves it below: final state is mixed
        return [_post(env, h, "income", w, rnd.randint(50, 300), exp, inc),
                _post(env, h, "expense", w, rnd.randint(50, 300), exp, inc)]

    await _run(real_engine, 100, 1, TARGET - 100, calls)


@pytest.mark.anyio
async def test_parallel_plus_and_plus_over_threshold_notify_once(real_engine):
    def calls(env, h, wids, exp, inc, rnd, before):
        w = wids[0]
        if before[w][0]:  # reached: bring the balance back below the goal first, in a round
            return [_post(env, h, "expense", w, before[w][1] - TARGET + 500, exp, inc)]
        return [_post(env, h, "income", w, 400, exp, inc),
                _post(env, h, "income", w, 400, exp, inc)]

    def once(before, after):  # both only add: exactly one transition per reach
        return 1 if after[next(iter(after))][0] and not before[next(iter(before))][0] else 0

    await _run(real_engine, 40, 1, TARGET - 500, calls, exact=once)


@pytest.mark.anyio
async def test_parallel_minus_and_minus_below_threshold_clear_flag(real_engine):
    def calls(env, h, wids, exp, inc, rnd, before):
        w = wids[0]
        if not before[w][0]:
            return [_post(env, h, "income", w, TARGET + 300 - before[w][1], exp, inc)]
        return [_post(env, h, "expense", w, 200, exp, inc),
                _post(env, h, "expense", w, 200, exp, inc)]

    await _run(real_engine, 40, 1, TARGET + 300, calls)


@pytest.mark.anyio
async def test_parallel_transfer_and_expense_keep_flag_equal_to_balance(real_engine):
    def calls(env, h, wids, exp, inc, rnd, before):
        a, b = wids
        return [_post(env, h, "transfer", a, rnd.randint(50, 300), exp, inc, to_wallet=b),
                _post(env, h, "expense", b, rnd.randint(50, 300), exp, inc),
                _post(env, h, "income", a, rnd.randint(50, 300), exp, inc)]

    await _run(real_engine, 60, 2, TARGET, calls)


@pytest.mark.anyio
async def test_opposite_transfers_keep_flags_and_never_fail(real_engine):
    def calls(env, h, wids, exp, inc, rnd, before):
        a, b = wids
        return [_post(env, h, "transfer", a, 100, exp, inc, to_wallet=b),
                _post(env, h, "transfer", b, 100, exp, inc, to_wallet=a)]

    await _run(real_engine, 40, 2, TARGET, calls)


# --- P4: delete / leave / ownership request in parallel -------------------------------------

@pytest.mark.anyio
@pytest.mark.parametrize("mover", ["leave", "remove"])
async def test_transfer_request_racing_with_leave_or_remove_sends_no_offer(real_engine, mover):
    from sqlalchemy import func

    from app.models.ownership_transfer import OwnershipTransfer
    from tests.test_ux_r9_transfer_deadlock import _seed_family

    factory = async_sessionmaker(real_engine, expire_on_commit=False)
    bad: list[str] = []
    for i in range(25):
        budget_id, owner_tid, members = await _seed_family(factory, 1)
        mtid, mid = members[0]
        async with _Env(factory) as env:
            ho = bearer_header_for_telegram_id(owner_tid)
            hm = bearer_header_for_telegram_id(mtid)
            move = (env.client.post("/api/v1/members/leave", headers=hm) if mover == "leave"
                    else env.client.delete(f"/api/v1/members/{mid}", headers=ho))
            rs = await asyncio.gather(
                env.client.post(f"/api/v1/members/{mid}/transfer", headers=ho), move)
            await env.goal_notify.drain_background()
        req, mv = rs
        async with factory() as s:
            pending = await s.scalar(
                select(func.count()).select_from(OwnershipTransfer).where(
                    OwnershipTransfer.to_user_id == mid, OwnershipTransfer.status == "pending"))
            rows = await s.scalar(
                select(func.count()).select_from(OwnershipTransfer).where(
                    OwnershipTransfer.to_user_id == mid))
            member_budget = await s.scalar(select(User.family_budget_id).where(User.id == mid))
        left = member_budget != budget_id
        if req.status_code >= 500 or mv.status_code >= 500:
            bad.append(f"{i}: 5xx {req.status_code}/{mv.status_code}")
        if left and pending:
            bad.append(f"{i}: member gone, offer still pending (request {req.status_code})")
        if req.status_code != 200 and rows:
            bad.append(f"{i}: request {req.status_code} but an offer row exists")
        if req.status_code == 200 and not rows:
            bad.append(f"{i}: request 200 without an offer")
    assert not bad, bad[:5]


# --- security r3: accept || new request from the owner ---------------------------------------

@pytest.mark.anyio
async def test_accept_racing_with_new_owner_request_keeps_one_owner_and_accepted_row(real_engine):
    from sqlalchemy import func

    from app.models.ownership_transfer import OwnershipTransfer
    from app.services.ownership_transfer import accept_ownership_transfer
    from tests.test_ux_r9_transfer_deadlock import _seed_family

    factory = async_sessionmaker(real_engine, expire_on_commit=False)
    bad: list[str] = []
    for i in range(100):
        budget_id, owner_tid, members = await _seed_family(factory, 2)
        (btid, bid), (_, cid) = members
        async with factory() as s:
            owner_id = await s.scalar(select(User.id).where(User.telegram_id == owner_tid))
            offer = OwnershipTransfer(family_budget_id=budget_id, from_user_id=owner_id,
                                      to_user_id=bid, status="pending")
            s.add(offer)
            await s.commit()
            offer_id = offer.id

        async def accept():
            try:
                async with factory() as s:
                    actor = await s.get(User, bid)
                    await accept_ownership_transfer(
                        s, transfer_id=offer_id, actor=actor, bot=None)
                    await s.commit()
                return "ok"
            except Exception as exc:  # noqa: BLE001
                return type(exc).__name__

        async with _Env(factory) as env:
            ho = bearer_header_for_telegram_id(owner_tid)
            acc, req = await asyncio.gather(
                accept(), env.client.post(f"/api/v1/members/{cid}/transfer", headers=ho))
            await env.goal_notify.drain_background()
        async with factory() as s:
            owners = await s.scalar(select(func.count()).select_from(User).where(
                User.family_budget_id == budget_id, User.role == "owner"))
            pending = await s.scalar(select(func.count()).select_from(OwnershipTransfer).where(
                OwnershipTransfer.family_budget_id == budget_id,
                OwnershipTransfer.status == "pending"))
            offer_status = await s.scalar(
                select(OwnershipTransfer.status).where(OwnershipTransfer.id == offer_id))
        if req.status_code >= 500:
            bad.append(f"{i}: owner request {req.status_code}")
        if acc not in ("ok", "TransferStaleError", "TransferNotPendingError"):
            bad.append(f"{i}: accept {acc}")
        if owners != 1:
            bad.append(f"{i}: owners {owners}")
        if pending > 1:
            bad.append(f"{i}: pending {pending}")
        if acc == "ok" and offer_status != "accepted":
            bad.append(f"{i}: accept ok but row is {offer_status}")
        if acc == "ok" and pending:
            bad.append(f"{i}: accepted, yet a pending offer from the former owner remains")
    assert not bad, bad[:5]
