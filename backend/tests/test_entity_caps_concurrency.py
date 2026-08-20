"""Concurrency tests for entity-cap enforcement (members, wallets).

Every cap in this app is enforced by "count active rows, then insert",
with nothing between the two steps to stop a concurrent request from doing
the same thing and pushing the count past the limit. These tests drive the
real production code paths (``app.services.entity_limits.lock_family_budget``,
``app.services.membership_lifecycle.count_active_members`` and the
``create_wallet`` endpoint function itself) against a real, file-based
SQLite database via aiosqlite — not a mock — so that the write-lock taken
by ``lock_family_budget`` actually serialises concurrent transactions the
same way a Postgres ``SELECT ... FOR UPDATE`` / row lock would in
production.

Note on SQLite and locking: SQLite silently drops a ``SELECT ... FOR
UPDATE`` clause (no error, no lock), which is why the fix in
``app/services/entity_limits.py`` takes the lock via a real no-op
``UPDATE`` statement instead — SQLite (like Postgres) must take a write
lock for an UPDATE, so the same defence is genuinely exercised by these
tests, not merely assumed to work because the driver "happened" to
serialise unrelated I/O.
"""

import asyncio
import tempfile
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.api.v1.wallets import create_wallet
from app.models.base import Base
from app.models.family_budget import FamilyBudget
from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.wallets_categories import WalletCreate
from app.services.entity_limits import (
    LIMIT_PERSONAL_WALLETS,
    LIMIT_SHARED_WALLETS,
    MEMBER_LIMIT,
    PERSONAL_WALLET_LIMIT,
    SHARED_WALLET_LIMIT,
    lock_family_budget,
)
from app.services.member_texts import invite_family_full_chat
from app.services.membership_lifecycle import count_active_members

pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# Shared sqlite fixture: a real, file-backed database so writer locking is
# genuinely exercised across separate connections/sessions, matching the
# pattern used in tests/test_security_hardening.py for the counter-increment
# race test.
# ---------------------------------------------------------------------------


@pytest.fixture
async def engine():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        eng = create_async_engine(f"sqlite+aiosqlite:///{tmp.name}")

        @event.listens_for(eng.sync_engine, "connect")
        def _fk(dbapi_connection, _):  # pragma: no cover - sqlite pragma plumbing
            dbapi_connection.execute("PRAGMA foreign_keys=ON")
            # Without a busy timeout, two writers racing for the same locked
            # row raise "database is locked" immediately instead of queuing.
            # A generous timeout lets SQLite actually serialise the writers,
            # which is the behaviour we are testing for.
            dbapi_connection.execute("PRAGMA busy_timeout=5000")

        async with eng.begin() as conn:
            await conn.run_sync(
                Base.metadata.create_all,
                tables=[
                    FamilyBudget.__table__,
                    User.__table__,
                    Wallet.__table__,
                ],
            )

        yield eng
        await eng.dispose()


async def _make_budget(engine, **kwargs) -> uuid.UUID:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        budget = FamilyBudget(**kwargs)
        session.add(budget)
        await session.commit()
        await session.refresh(budget)
        return budget.id


async def _add_users(engine, budget_id: uuid.UUID, count: int, *, role: str = "member") -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        for i in range(count):
            session.add(
                User(
                    telegram_id=1_000_000 + i,
                    family_budget_id=budget_id,
                    role="owner" if (i == 0 and role == "owner") else "member",
                    language="ru",
                )
            )
        await session.commit()


async def _count_users(engine, budget_id: uuid.UUID) -> int:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        return await count_active_members(session, budget_id)


# ---------------------------------------------------------------------------
# The join step below mirrors, statement for statement, the fixed
# transactional gate in bot/onboarding.py's language_callback: lock the
# budget row, count active members, refuse if at the cap, otherwise insert.
# It calls the real production helpers (lock_family_budget,
# count_active_members) rather than re-implementing the logic, so the actual
# fix under test is exercised, not a stand-in for it.
# ---------------------------------------------------------------------------


class FamilyFullRefusal(Exception):
    pass


async def _attempt_join(engine, budget_id: uuid.UUID, telegram_id: int) -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        async with session.begin():
            await lock_family_budget(session, budget_id)
            if await count_active_members(session, budget_id) >= MEMBER_LIMIT:
                raise FamilyFullRefusal(invite_family_full_chat())
            session.add(
                User(
                    telegram_id=telegram_id,
                    family_budget_id=budget_id,
                    role="member",
                    language="ru",
                )
            )


async def test_concurrent_joins_never_exceed_member_cap(engine) -> None:
    budget_id = await _make_budget(engine)
    await _add_users(engine, budget_id, MEMBER_LIMIT - 1)  # 3 of 4 slots filled

    concurrency = 8
    results = await asyncio.gather(
        *[_attempt_join(engine, budget_id, 2_000_000 + i) for i in range(concurrency)],
        return_exceptions=True,
    )

    successes = [r for r in results if r is None]
    refusals = [r for r in results if isinstance(r, FamilyFullRefusal)]
    other_errors = [r for r in results if r is not None and not isinstance(r, FamilyFullRefusal)]

    assert not other_errors, f"unexpected errors: {other_errors}"
    assert len(successes) == 1, "exactly one of the concurrent joins may fill the last slot"
    assert len(refusals) == concurrency - 1
    assert await _count_users(engine, budget_id) == MEMBER_LIMIT


async def test_losing_join_gets_existing_refusal_message(engine) -> None:
    budget_id = await _make_budget(engine)
    await _add_users(engine, budget_id, MEMBER_LIMIT)  # already full

    with pytest.raises(FamilyFullRefusal) as exc_info:
        await _attempt_join(engine, budget_id, 3_000_000)

    assert str(exc_info.value) == invite_family_full_chat()
    assert await _count_users(engine, budget_id) == MEMBER_LIMIT


async def test_bot_onboarding_member_join_wires_the_budget_lock() -> None:
    """Wiring check for bot/onboarding.py's language_callback (the member-join
    branch that actually inserts the User row). The concurrency tests above
    exercise lock_family_budget + count_active_members directly (mirroring
    the production statements exactly), but do not go through aiogram's
    language_callback itself. This test guards the wiring: if someone removes
    the `await lock_family_budget(...)` call from language_callback, this
    test fails even though the mechanism tests above still pass.
    """
    from bot.onboarding import language_callback

    session = SimpleNamespace(
        add=lambda _model: None,
        flush=AsyncMock(),
        execute=AsyncMock(),
        get=AsyncMock(
            return_value=SimpleNamespace(name="Семья Юсуповых", is_deleted=False)
        ),
    )

    class TransactionContext:
        async def __aenter__(self) -> None:
            return None

        async def __aexit__(self, *_args: object) -> None:
            return None

    session.begin = lambda: TransactionContext()

    class SessionContext:
        async def __aenter__(self) -> SimpleNamespace:
            return session

        async def __aexit__(self, *_args: object) -> None:
            return None

    message = SimpleNamespace(answer=AsyncMock(), delete=AsyncMock())
    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=456),
        message=message,
        data="lang:ru",
        answer=AsyncMock(),
    )
    state = SimpleNamespace(
        get_data=AsyncMock(
            return_value={
                "flow": "member",
                "telegram_id": 456,
                "family_budget_id": str(uuid.uuid4()),
                "first_name": "New",
                "username": "newbie",
            }
        ),
        clear=AsyncMock(),
    )
    bot = SimpleNamespace(get_me=AsyncMock())

    lock_mock = AsyncMock()
    with (
        patch("bot.onboarding.async_session_factory", return_value=SessionContext()),
        patch(
            "bot.onboarding.get_active_user_by_telegram_id",
            new=AsyncMock(return_value=None),
        ),
        patch("bot.onboarding.count_active_members", new=AsyncMock(return_value=1)),
        patch("bot.onboarding.assign_default_card_uzs", new=AsyncMock()),
        patch("bot.onboarding.lock_family_budget", new=lock_mock),
    ):
        await language_callback(callback, state, bot)

    lock_mock.assert_awaited_once()


async def test_sequential_join_at_cap_refused_as_before(engine) -> None:
    """No-regression check: a single request at the cap behaves exactly as
    it did before the fix (no concurrency involved)."""
    budget_id = await _make_budget(engine)
    await _add_users(engine, budget_id, MEMBER_LIMIT)

    with pytest.raises(FamilyFullRefusal):
        await _attempt_join(engine, budget_id, 4_000_000)
    assert await _count_users(engine, budget_id) == MEMBER_LIMIT


# ---------------------------------------------------------------------------
# Personal + shared wallet caps, driven through the real create_wallet
# endpoint function (app/api/v1/wallets.py) directly — same function FastAPI
# calls, just invoked without the HTTP layer, following the pattern of
# calling service functions directly used elsewhere in this suite.
# ---------------------------------------------------------------------------


async def _make_user(engine, budget_id: uuid.UUID, *, role: str = "member") -> User:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        user = User(
            telegram_id=5_000_000 + hash((budget_id, role)) % 1000,
            family_budget_id=budget_id,
            role=role,
            language="ru",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _attempt_create_wallet(engine, user: User, *, is_personal: bool) -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        # Re-attach a lightweight copy of the user to this session's identity
        # map; SQLAlchemy ORM objects are not safe to share across sessions.
        local_user = await session.get(User, user.id)
        body = WalletCreate(name="Wallet", currency="UZS", is_personal=is_personal)
        await create_wallet(body, local_user, session)


async def _count_wallets(engine, budget_id: uuid.UUID, *, is_personal: bool) -> int:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        stmt = (
            select(func.count())
            .select_from(Wallet)
            .where(
                Wallet.family_budget_id == budget_id,
                Wallet.is_deleted.is_(False),
                Wallet.is_personal.is_(is_personal),
            )
        )
        return int(await session.scalar(stmt) or 0)


async def test_concurrent_personal_wallet_creates_never_exceed_cap(engine) -> None:
    budget_id = await _make_budget(engine)
    user = await _make_user(engine, budget_id, role="member")

    # Fill PERSONAL_WALLET_LIMIT - 1 wallets for this user up front.
    async with AsyncSession(engine, expire_on_commit=False) as session:
        for _ in range(PERSONAL_WALLET_LIMIT - 1):
            session.add(
                Wallet(
                    family_budget_id=budget_id,
                    name="Wallet",
                    currency="UZS",
                    is_personal=True,
                    owner_user_id=user.id,
                )
            )
        await session.commit()

    concurrency = 6
    results = await asyncio.gather(
        *[_attempt_create_wallet(engine, user, is_personal=True) for _ in range(concurrency)],
        return_exceptions=True,
    )

    successes = [r for r in results if r is None]
    refusals = [r for r in results if isinstance(r, HTTPException) and r.status_code == 409]
    other_errors = [
        r for r in results if r is not None and not (isinstance(r, HTTPException) and r.status_code == 409)
    ]

    assert not other_errors, f"unexpected errors: {other_errors}"
    assert len(successes) == 1
    assert len(refusals) == concurrency - 1
    assert all(r.detail == LIMIT_PERSONAL_WALLETS for r in refusals)
    assert await _count_wallets(engine, budget_id, is_personal=True) == PERSONAL_WALLET_LIMIT


async def test_concurrent_shared_wallet_creates_never_exceed_cap(engine) -> None:
    budget_id = await _make_budget(engine)
    owner = await _make_user(engine, budget_id, role="owner")

    async with AsyncSession(engine, expire_on_commit=False) as session:
        for _ in range(SHARED_WALLET_LIMIT - 1):
            session.add(
                Wallet(
                    family_budget_id=budget_id,
                    name="Shared",
                    currency="UZS",
                    is_personal=False,
                    owner_user_id=None,
                )
            )
        await session.commit()

    concurrency = 5
    results = await asyncio.gather(
        *[_attempt_create_wallet(engine, owner, is_personal=False) for _ in range(concurrency)],
        return_exceptions=True,
    )

    successes = [r for r in results if r is None]
    refusals = [r for r in results if isinstance(r, HTTPException) and r.status_code == 409]

    assert len(successes) == 1
    assert len(refusals) == concurrency - 1
    assert all(r.detail == LIMIT_SHARED_WALLETS for r in refusals)
    assert await _count_wallets(engine, budget_id, is_personal=False) == SHARED_WALLET_LIMIT


async def test_sequential_wallet_create_at_cap_refused_as_before(engine) -> None:
    budget_id = await _make_budget(engine)
    user = await _make_user(engine, budget_id, role="member")
    async with AsyncSession(engine, expire_on_commit=False) as session:
        for _ in range(PERSONAL_WALLET_LIMIT):
            session.add(
                Wallet(
                    family_budget_id=budget_id,
                    name="Wallet",
                    currency="UZS",
                    is_personal=True,
                    owner_user_id=user.id,
                )
            )
        await session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await _attempt_create_wallet(engine, user, is_personal=True)
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == LIMIT_PERSONAL_WALLETS
    assert await _count_wallets(engine, budget_id, is_personal=True) == PERSONAL_WALLET_LIMIT
