"""ux-next6 L2: PATCH /me is guarded like every other write; the bot never uses a default wallet of another family
or another person's personal wallet. Real parallel connections (harness of test_ux_r14)."""
from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db import get_session
from app.main import app
from app.models.family_budget import FamilyBudget
from app.models.user import User
from app.models.wallet import Wallet
from tests.auth_helpers import TEST_APP_PASS_SECRET
from tests.test_ux_r14_write_during_family_change import World, real_engine  # noqa: F401
from tests.test_wallets_categories import _db_available

pytestmark = [pytest.mark.skipif(not _db_available(), reason="postgres not available"), pytest.mark.anyio]


async def test_patch_me_during_leave_is_refused_and_default_wallet_stays_clean(real_engine):
    factory = async_sessionmaker(real_engine, expire_on_commit=False)
    w = await World(factory).seed(as_member=True)

    async def per_request_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = per_request_session
    started = asyncio.Event()
    try:
        with patch("app.main.verify_postgres_connection", new=AsyncMock()), patch(
            "app.auth.deps.APP_PASS_SECRET", TEST_APP_PASS_SECRET
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                changer = asyncio.create_task(w.change_family("leave", started))
                await started.wait()
                resp = await c.patch("/api/v1/me", headers=w.headers,
                                     json={"default_wallet_id": str(w.shared)})
                await changer
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 409
    assert resp.json()["detail"] == "family_changed"
    async with factory() as s:
        me = await s.get(User, w.me_id)
        dw = await s.get(Wallet, me.default_wallet_id) if me.default_wallet_id else None
        assert dw is None or dw.family_budget_id == me.family_budget_id


async def test_bot_default_wallet_ignores_foreign_family_and_foreign_personal(real_engine):
    from bot.quick_entry.handlers import _get_default_wallet
    from bot.quick_entry.receipt_photo import _get_default_wallet as photo_default

    factory = async_sessionmaker(real_engine, expire_on_commit=False)
    w = await World(factory).seed(as_member=True)
    async with factory() as s:
        other = await s.scalar(select(User).where(User.telegram_id == w.other_tid))
        foreign_personal = Wallet(
            family_budget_id=w.old_id, name="Чужой личный", currency="UZS",
            is_personal=True, owner_user_id=other.id,
        )
        other_budget = FamilyBudget(invite_token=f"rc-{uuid.uuid4()}")
        s.add_all([foreign_personal, other_budget])
        await s.flush()
        foreign_family = Wallet(
            family_budget_id=other_budget.id, name="Чужая семья", currency="UZS", is_personal=False
        )
        s.add(foreign_family)
        await s.commit()
        fp_id, ff_id = foreign_personal.id, foreign_family.id
    for bad in (fp_id, ff_id):
        async with factory() as s:
            me = await s.get(User, w.me_id)
            me.default_wallet_id = bad
            await s.flush()
            for fn in (_get_default_wallet, photo_default):
                chosen = await fn(s, me)
                assert chosen is not None
                assert chosen.id != bad
                assert chosen.family_budget_id == me.family_budget_id
                assert not chosen.is_personal or chosen.owner_user_id == me.id
            await s.rollback()
