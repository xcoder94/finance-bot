"""ux-r11: mixed naive/aware dates never give 500; deferred phone request is sent safely."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from tests.test_history_analytics import (  # noqa: F401
    api_client,
    auth_headers,
    create_user_with_budget,
    pytestmark,
)

NAIVE = "2026-01-01T00:00:00"
AWARE = "2026-02-01T00:00:00Z"


def _tg() -> int:
    return int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000


@pytest.mark.parametrize(
    "path,extra",
    [
        ("analytics/expenses-by-category", {"currency": "UZS"}),
        ("analytics/expense-comparison", {"currency": "UZS"}),
        ("analytics/expenses-by-subcategory", {"currency": "UZS"}),
        ("analytics/income-by-category", {"currency": "UZS"}),
        ("analytics/summary", {}),
        ("analytics/personal-summary", {}),
        ("transactions/history", {}),
    ],
)
@pytest.mark.parametrize("naive_first", [True, False])
async def test_mixed_naive_and_aware_dates_are_not_a_server_error(
    api_client: tuple[AsyncClient, AsyncSession], path, extra, naive_first  # noqa: F811
) -> None:
    client, session = api_client
    tg = _tg()
    _user, budget = await create_user_with_budget(session, telegram_id=tg)
    params = dict(extra)
    if path.endswith("expenses-by-subcategory"):
        parent = ExpenseCategory(family_budget_id=budget.id, name="P")
        session.add(parent)
        await session.flush()
        params["parent_category_id"] = str(parent.id)
    a, b = (NAIVE, AWARE) if naive_first else (AWARE, "2026-03-01T00:00:00")
    # naive_first: from naive 01-01 .. to aware 02-01; else from aware 02-01 .. to naive 03-01
    resp = await client.get(
        f"/api/v1/{path}", headers=auth_headers(tg), params={**params, "date_from": a, "date_to": b}
    )
    assert resp.status_code == 200, resp.text


async def test_naive_dates_are_read_as_utc(
    api_client: tuple[AsyncClient, AsyncSession],  # noqa: F811
) -> None:
    client, session = api_client
    tg = _tg()
    await create_user_with_budget(session, telegram_id=tg)
    # naive from > aware to (in UTC) is still the ordinary 422, not 500
    resp = await client.get(
        "/api/v1/analytics/summary",
        headers=auth_headers(tg),
        params={"date_from": "2026-03-01T00:00:00", "date_to": AWARE},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------- phone request (L3)

import asyncio  # noqa: E402
import time  # noqa: E402
from datetime import UTC, datetime  # noqa: E402
from unittest.mock import AsyncMock  # noqa: E402

from sqlalchemy import select  # noqa: E402

from app.models.user import User  # noqa: E402
from app.services import deferred_phone_prompt as dpp  # noqa: E402
from app.services import goal_notify  # noqa: E402
from tests.test_ux_p6_phone import _add_ops, _eligible_user, _Same  # noqa: E402
from tests.test_quick_entry_flow import rollback_session  # noqa: E402


def _patch_bot(monkeypatch, send) -> AsyncMock:  # noqa: ANN001
    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=send)

    async def fake_resolve_bot(_b):  # noqa: ANN001
        return bot, False

    monkeypatch.setattr("app.services.goal_notify.resolve_bot", fake_resolve_bot)
    return bot


async def _third_op(session, user, budget, wallet, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(dpp, "SEND_DELAY_SECONDS", 0)
    monkeypatch.setattr(dpp, "async_session_factory", lambda: _Same(session))
    await _add_ops(session, user, budget, wallet, 3)
    await session.commit()


async def test_hanging_telegram_does_not_hold_the_prompt_for_a_minute(monkeypatch) -> None:
    async def hang(*_a, **_k):  # noqa: ANN002, ANN003
        await asyncio.sleep(30)

    monkeypatch.setattr(goal_notify, "NOTICE_TIMEOUT_SECONDS", 0.3)
    bot = _patch_bot(monkeypatch, hang)
    async with rollback_session() as session:
        user, budget, wallet = await _eligible_user(session, tid=9_611_001)
        t0 = time.monotonic()
        await _third_op(session, user, budget, wallet, monkeypatch)  # commit returns at once
        assert time.monotonic() - t0 < 0.25
        await dpp.drain()
        assert time.monotonic() - t0 < 3  # the send was cut by the short timeout
        assert bot.send_message.await_count == 1  # it did try, through the safe path


async def test_prompt_is_sent_once_with_text_and_button(monkeypatch) -> None:
    bot = _patch_bot(monkeypatch, AsyncMock())
    async with rollback_session() as session:
        user, budget, wallet = await _eligible_user(session, tid=9_611_002)
        await _third_op(session, user, budget, wallet, monkeypatch)
        await dpp.drain()
        await _add_ops(session, user, budget, wallet, 1)
        await session.commit()
        await dpp.drain()
        assert bot.send_message.await_count == 1
        assert bot.send_message.await_args.args[0] == user.telegram_id
        assert bot.send_message.await_args.kwargs.get("reply_markup") is not None


async def test_failed_send_is_asked_again_on_a_later_operation_then_only_once(
    monkeypatch,
) -> None:
    attempts: list[int] = []

    async def flaky(chat_id, *_a, **_k):  # noqa: ANN001, ANN002, ANN003
        attempts.append(chat_id)
        if len(attempts) == 1:
            raise RuntimeError("telegram down")

    _patch_bot(monkeypatch, flaky)
    async with rollback_session() as session:
        user, budget, wallet = await _eligible_user(session, tid=9_611_003)
        await _third_op(session, user, budget, wallet, monkeypatch)
        await dpp.drain()
        assert len(attempts) == 1  # failed: the person has not got it yet
        fresh = await session.scalar(select(User).where(User.id == user.id))
        await session.refresh(fresh)
        assert fresh.phone_prompted_at is None  # so the next operation asks again
        await _add_ops(session, user, budget, wallet, 1)
        await session.commit()
        await dpp.drain()
        assert len(attempts) == 2  # delivered now
        await _add_ops(session, user, budget, wallet, 1)
        await session.commit()
        await dpp.drain()
        assert len(attempts) == 2  # and never a third time
