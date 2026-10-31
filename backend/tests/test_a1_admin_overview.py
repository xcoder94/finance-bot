"""a-1: GET /api/v1/admin/overview on a fixture with known dates (Tashkent, 19:00 UTC edge)."""

import json
import socket
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.admin_helpers import (
    FORBIDDEN_KEY_PARTS,
    add_activity,
    make_admin,
    make_user,
    tashkent_noon,
    utc,
    walk_keys,
)
from tests.db_helpers import db_address
from tests.test_wallets_categories import api_client, auth_headers  # noqa: F401


def _db_available() -> bool:
    try:
        with socket.create_connection(db_address(), timeout=1):
            return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available"),
    pytest.mark.anyio,
]

TODAY = date(2026, 6, 15)
NOW = utc(2026, 6, 15, 7)  # 12:00 Tashkent


async def _setup(api_client, monkeypatch):
    client, session = api_client
    admin = await make_user(session, created_at=utc(2026, 1, 1))
    make_admin(monkeypatch, admin.telegram_id)
    monkeypatch.setattr("app.api.v1.admin.utcnow", lambda: NOW)
    headers = auth_headers(admin.telegram_id)

    async def get() -> dict:
        resp = await client.get("/api/v1/admin/overview", headers=headers)
        assert resp.status_code == 200, resp.text
        return resp.json()

    return client, session, admin, get


async def test_growth_numbers_on_known_dates(api_client, monkeypatch) -> None:
    client, session, admin, get = await _setup(api_client, monkeypatch)
    before = await get()

    # registration instants around the Tashkent midnight (19:00 UTC)
    a = await make_user(session, created_at=utc(2026, 6, 14, 19, 0, 0))  # today 00:00 T
    shared = a.family_budget_id
    from app.models.family_budget import FamilyBudget

    fam_a = await session.get(FamilyBudget, shared)
    b = await make_user(  # yesterday 23:59:59 T, member of A's family
        session, created_at=utc(2026, 6, 14, 18, 59, 59), family=fam_a, role="member"
    )
    c = await make_user(session, created_at=utc(2026, 6, 8, 19, 0, 0))  # T-6 00:00 -> in 7d
    d = await make_user(session, created_at=utc(2026, 6, 8, 18, 59, 59))  # T-7 -> only 30d
    e = await make_user(session, created_at=utc(2026, 5, 16, 19, 0, 0))  # T-29 00:00 -> in 30d
    f = await make_user(session, created_at=utc(2026, 5, 16, 18, 59, 59))  # T-30 -> out
    await make_user(  # deleted user + deleted family: counted nowhere
        session, created_at=utc(2026, 6, 15, 1), is_deleted=True, family_deleted=True
    )

    # activity
    await add_activity(session, a, date(2026, 6, 15))
    await add_activity(session, a, date(2026, 6, 14), app=False, bot=True)
    await add_activity(session, a, date(2026, 6, 12))
    await add_activity(session, b, date(2026, 6, 9), app=False, bot=True)  # T-6: WAU edge
    await add_activity(session, c, date(2026, 6, 8))  # T-7: out of WAU, in MAU
    await add_activity(session, d, date(2026, 5, 17))  # T-29: MAU edge
    await add_activity(session, e, date(2026, 5, 16))  # T-30: out of MAU; sets "since"
    await add_activity(session, f, date(2026, 6, 16))  # future day: ignored everywhere

    after = await get()

    assert after["totals"]["users"] - before["totals"]["users"] == 6
    # families of a(+b), c, d, e, f = 5
    assert after["totals"]["families"] - before["totals"]["families"] == 5
    assert after["totals"]["families_multi"] - before["totals"]["families_multi"] == 1

    def delta(block: str, key: str) -> int:
        return after[block][key] - before[block][key]

    assert (delta("new_users", "today"), delta("new_users", "d7"), delta("new_users", "d30")) == (
        1,
        3,
        5,
    )
    # a's family is created at a's instant; b joined it. families: a-fam today, c in 7, d/e in 30
    assert (
        delta("new_families", "today"),
        delta("new_families", "d7"),
        delta("new_families", "d30"),
    ) == (1, 2, 4)

    assert after["active"] == {"dau": 1, "wau": 2, "mau": 4}

    chart = after["daily_active"]
    assert len(chart) == 30
    assert chart[0] == {"day": "2026-05-17", "users": 1}
    assert chart[-1] == {"day": "2026-06-15", "users": 1}
    by_day = {p["day"]: p["users"] for p in chart}
    assert {k: v for k, v in by_day.items() if v} == {
        "2026-05-17": 1,
        "2026-06-08": 1,
        "2026-06-09": 1,
        "2026-06-12": 1,
        "2026-06-14": 1,
        "2026-06-15": 1,
    }
    assert after["activity_since"] == "2026-05-16"

    # cohort D7 = [05-03..06-01] registered after "since" (05-16): e (05-17 Tashkent) only,
    # window 05-24..05-30 has no activity -> 0 of 1.
    assert after["retention"]["d7"] == {"returned": 0, "cohort": 1, "percent": 0.0}
    assert after["retention"]["d30"] == {"returned": 0, "cohort": 0, "percent": None}


async def test_retention_cohorts_and_windows(api_client, monkeypatch) -> None:
    client, session, admin, get = await _setup(api_client, monkeypatch)

    async def reg(y, m, d, **kw):
        return await make_user(session, created_at=tashkent_noon(y, m, d), **kw)

    s0 = await reg(2026, 4, 1)
    await add_activity(session, s0, date(2026, 5, 1))  # "since" = 05-01
    p1 = await reg(2026, 5, 3)
    for day in (date(2026, 5, 10), date(2026, 6, 2)):  # reg+7 / reg+30
        await add_activity(session, p1, day)
    p2 = await reg(2026, 5, 9)
    for day in (date(2026, 5, 22), date(2026, 6, 14)):  # reg+13 / reg+36
        await add_activity(session, p2, day)
    p3 = await reg(2026, 5, 5)
    for day in (date(2026, 5, 11), date(2026, 5, 19), date(2026, 6, 3), date(2026, 6, 11)):
        await add_activity(session, p3, day)  # reg+6, +14, +29, +37: all outside windows
    await reg(2026, 5, 2)  # p4: D30 cohort, no activity
    p5 = await reg(2026, 5, 1)  # reg == since: excluded from both cohorts
    await add_activity(session, p5, date(2026, 5, 8))
    await add_activity(session, p5, date(2026, 6, 1))
    p6 = await reg(2026, 5, 12)
    await add_activity(session, p6, date(2026, 5, 19))  # reg+7
    p7 = await reg(2026, 6, 1)  # T-14: upper edge of the D7 cohort
    await add_activity(session, p7, date(2026, 6, 8))
    p8 = await reg(2026, 6, 2)  # T-13: not in the cohort yet
    await add_activity(session, p8, date(2026, 6, 9))

    data = await get()
    assert data["retention"]["d7"] == {"returned": 4, "cohort": 5, "percent": 80.0}
    assert data["retention"]["d30"] == {"returned": 2, "cohort": 4, "percent": 50.0}
    assert data["activity_since"] == "2026-05-01"


async def test_empty_activity_table(api_client, monkeypatch) -> None:
    client, session, admin, get = await _setup(api_client, monkeypatch)
    data = await get()
    assert data["activity_since"] is None
    assert data["active"] == {"dau": 0, "wau": 0, "mau": 0}
    assert data["retention"]["d7"] == {"returned": 0, "cohort": 0, "percent": None}
    assert data["retention"]["d30"] == {"returned": 0, "cohort": 0, "percent": None}
    assert len(data["daily_active"]) == 30
    assert all(p["users"] == 0 for p in data["daily_active"])


async def test_overview_has_no_money_or_names(api_client, monkeypatch) -> None:
    client, session, admin, get = await _setup(api_client, monkeypatch)
    from datetime import UTC, datetime

    from app.models.family_budget import FamilyBudget
    from app.models.income_category import IncomeCategory
    from app.models.transaction import Transaction
    from app.models.wallet import Wallet

    u = await make_user(session, created_at=NOW, first_name="SecretPerson")
    fam = await session.get(FamilyBudget, u.family_budget_id)
    fam.name = "SecretFamilyName"
    w = Wallet(family_budget_id=fam.id, name="SecretWalletName", currency="UZS")
    cat = IncomeCategory(family_budget_id=fam.id, name="SecretCategory")
    session.add_all([w, cat])
    await session.flush()
    session.add(
        Transaction(
            family_budget_id=fam.id,
            type="income",
            wallet_id=w.id,
            amount=7654321,
            income_category_id=cat.id,
            comment="SecretComment",
            created_by_user_id=u.id,
            transaction_date=datetime.now(UTC),
        )
    )
    await add_activity(session, u, TODAY)
    await session.flush()

    data = await get()
    body = json.dumps(data, ensure_ascii=False)
    for key in walk_keys(data):
        assert not any(part in key.lower() for part in FORBIDDEN_KEY_PARTS), key
    for secret in ("7654321", "SecretFamilyName", "SecretWalletName", "SecretCategory", "SecretComment", "SecretPerson"):
        assert secret not in body


async def test_families_multi_ignores_deleted_family(api_client, monkeypatch) -> None:
    """Kills M11: a deleted family with 2 live members is not a multi-member family."""
    client, session, admin, get = await _setup(api_client, monkeypatch)
    before = await get()
    from app.models.family_budget import FamilyBudget

    dead = await make_user(session, family_deleted=True)
    dead_fam = await session.get(FamilyBudget, dead.family_budget_id)
    await make_user(session, family=dead_fam, role="member")
    after = await get()
    assert after["totals"]["families_multi"] == before["totals"]["families_multi"]
    assert after["totals"]["families"] == before["totals"]["families"]


async def test_deleted_users_are_not_in_active_counts_or_chart(api_client, monkeypatch) -> None:
    client, session, admin, get = await _setup(api_client, monkeypatch)
    before = await get()
    today = date.fromisoformat(before["daily_active"][-1]["day"])
    live = await make_user(session)
    gone = await make_user(session, is_deleted=True)
    await add_activity(session, live, today)
    await add_activity(session, gone, today)
    after = await get()
    assert after["active"]["dau"] - before["active"]["dau"] == 1
    assert after["active"]["wau"] - before["active"]["wau"] == 1
    assert after["active"]["mau"] - before["active"]["mau"] == 1
    assert after["daily_active"][-1]["users"] - before["daily_active"][-1]["users"] == 1
