"""a-2: GET /api/v1/admin/usage - operations by channel (Tashkent day edge, demo/deleted excluded)."""

import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pytest

from app.models.transaction import Transaction
from app.models.wallet import Wallet
from tests.admin_helpers import (
    FORBIDDEN_KEY_PARTS,
    make_admin,
    make_user,
    utc,
    walk_keys,
)
from tests.test_a1_admin_overview import pytestmark  # noqa: F401
from tests.test_wallets_categories import api_client, auth_headers  # noqa: F401

NOW = utc(2026, 6, 15, 7)  # 12:00 Tashkent, 15 June
DAY_START = utc(2026, 6, 14, 19)  # 00:00 Tashkent 15 June
URL = "/api/v1/admin/usage"
ALL_KEYS = {"text", "voice", "photo", "app", "unknown", "total"}


async def _setup(api_client, monkeypatch):
    client, session = api_client
    admin = await make_user(session, created_at=utc(2026, 1, 1))
    make_admin(monkeypatch, admin.telegram_id)
    monkeypatch.setattr("app.api.v1.admin.utcnow", lambda: NOW)
    wallet = Wallet(family_budget_id=admin.family_budget_id, name="W", currency="UZS")
    session.add(wallet)
    await session.flush()
    headers = auth_headers(admin.telegram_id)

    async def op(channel, created_at: datetime, *, demo=False, deleted=False) -> None:
        session.add(
            Transaction(
                family_budget_id=admin.family_budget_id, type="expense", wallet_id=wallet.id,
                amount=1, created_by_user_id=admin.id, transaction_date=created_at,
                created_at=created_at, channel=channel, is_demo=demo, is_deleted=deleted,
            )
        )
        await session.flush()

    async def get(period="day") -> dict:
        resp = await client.get(URL, params={"period": period}, headers=headers)
        assert resp.status_code == 200, resp.text
        return resp.json()

    return client, session, headers, op, get


async def test_counts_by_channel_each_period_and_day_edge(api_client, monkeypatch) -> None:
    client, session, headers, op, get = await _setup(api_client, monkeypatch)
    from datetime import timedelta

    # today (>= 19:00 UTC on the 14th): text x2, voice, photo, app, NULL
    for ch in ("text", "text", "voice", "photo", "app", None):
        await op(ch, DAY_START + timedelta(hours=3))
    await op("text", DAY_START)  # exactly 00:00 Tashkent: inside
    await op("text", DAY_START - timedelta(seconds=1))  # 23:59:59 yesterday: outside "day"
    await op("app", utc(2026, 6, 10, 7))  # 5 days ago: week + month
    await op("voice", utc(2026, 5, 20, 7))  # 26 days ago: month only
    await op("photo", utc(2026, 5, 1, 7))  # outside all
    # excluded: demo and deleted
    await op("text", NOW, demo=True)
    await op("app", NOW, deleted=True)

    day = await get("day")
    assert day["period"] == "day"
    assert day["operations"] == {"text": 3, "voice": 1, "photo": 1, "app": 1, "unknown": 1, "total": 7}
    week = await get("week")
    assert week["operations"] == {"text": 4, "voice": 1, "photo": 1, "app": 2, "unknown": 1, "total": 9}
    month = await get("month")
    assert month["operations"] == {"text": 4, "voice": 2, "photo": 1, "app": 2, "unknown": 1, "total": 10}
    for body in (day, week, month):
        ops = body["operations"]
        assert ops["total"] == sum(v for k, v in ops.items() if k != "total")


async def test_empty_gives_zeros_and_period_defaults_to_day(api_client, monkeypatch) -> None:
    client, session, headers, op, get = await _setup(api_client, monkeypatch)
    body = (await client.get(URL, headers=headers)).json()
    assert body["period"] == "day"
    assert body["operations"] == {k: 0 for k in ALL_KEYS}


async def test_ai_block_is_present_and_zero_without_usage(api_client, monkeypatch) -> None:
    client, session, headers, op, get = await _setup(api_client, monkeypatch)
    ai = (await get("week"))["ai"]
    assert ai["calls"] == 0 and ai["messages"] == 0 and ai["cost_usd"] == 0


@pytest.mark.parametrize("bad", ["year", "", "DAY", "1", "day;drop"])
async def test_bad_period_is_422(api_client, monkeypatch, bad) -> None:
    client, session, headers, op, get = await _setup(api_client, monkeypatch)
    assert (await client.get(URL, params={"period": bad}, headers=headers)).status_code == 422


async def test_non_admin_404_no_token_401_write_405(api_client, monkeypatch) -> None:
    client, session, headers, op, get = await _setup(api_client, monkeypatch)
    other = await make_user(session)
    assert (await client.get(URL)).status_code == 401
    resp = await client.get(URL, headers=auth_headers(other.telegram_id))
    assert resp.status_code == 404 and resp.json() == {"detail": "Not Found"}
    assert (await client.post(URL, headers=headers)).status_code == 405


async def test_response_keys_are_counts_only(api_client, monkeypatch) -> None:
    client, session, headers, op, get = await _setup(api_client, monkeypatch)
    await op("text", NOW)
    body = await get("month")
    assert set(body) == {"period", "operations", "ai"}
    assert set(body["operations"]) == ALL_KEYS
    for key in walk_keys(body):
        assert not any(bad in key.lower() for bad in FORBIDDEN_KEY_PARTS), key
    assert all(isinstance(v, int) for v in body["operations"].values())


def test_main_installs_access_log_query_filter_in_a_fresh_process() -> None:
    """Kills mutant N15: nothing else may have installed the filter before app.main is imported."""
    code = (
        "import logging\n"
        "lg = logging.getLogger('uvicorn.access')\n"
        "assert not any(getattr(f, '_strips_query', False) for f in lg.filters)\n"
        "import app.main\n"
        "assert any(getattr(f, '_strips_query', False) for f in lg.filters)\n"
    )
    backend = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "-c", code], cwd=backend, capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, proc.stderr[-800:]
