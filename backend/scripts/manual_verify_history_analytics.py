"""
Automated manual verification of Acceptance criteria in
docs/tasks/06-api-history-analytics.md.

Prerequisites:
  1. Server running: uvicorn app.main:app --reload (port 8000)
  2. Owner (telegram_id=111111) and Member (telegram_id=222222) exist in DB.

Run (from backend/, with venv active):
    python -m scripts.manual_verify_history_analytics

Design note: the family's test data is never cleaned between runs (project
convention), so this script never asserts absolute totals across the whole
family. Instead it either (a) filters by category/subcategory ids it just
created — those ids cannot have pre-existing data — or (b) captures a
baseline snapshot before inserting its own transactions and asserts the
delta after insertion.
"""

import asyncio
import sys
import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import select

from app.db import async_session_factory
from app.models.expense_category import ExpenseCategory
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.history_analytics import default_calendar_year_range, elapsed_days_in_period
from scripts.gen_test_initdata import build_init_data

BASE_URL = "http://127.0.0.1:8000"
OWNER_TELEGRAM_ID = 111111
MEMBER_TELEGRAM_ID = 222222

passed = 0
failed = 0


def check(label: str, condition: bool, extra: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed += 1
        detail = f"  {extra}" if extra else ""
        print(f"  [FAIL] {label}{detail}")


def close_enough(actual: float, expected: float, tolerance: float = 1) -> bool:
    """Rounding convention (floor vs round) isn't pinned down by the spec
    for average_daily_expense, so allow +/-1 instead of exact equality."""
    return abs(actual - expected) <= tolerance


def auth_header(telegram_id: int, first_name: str) -> dict[str, str]:
    return {
        "Authorization": "tma "
        + build_init_data(
            telegram_id=telegram_id,
            first_name=first_name,
            last_name=None,
            username=None,
            language_code="ru",
            auth_date=None,
        ),
    }


async def fetch_all_history(client, headers, date_from, date_to, page_size=100):
    """Pages through the full history result set for the given range."""
    items: list[dict] = []
    offset = 0
    total_count = None
    while True:
        resp = await client.get(
            "/api/v1/transactions/history",
            headers=headers,
            params={"date_from": date_from, "date_to": date_to, "limit": page_size, "offset": offset},
        )
        if resp.status_code != 200:
            return items, total_count, resp
        body = resp.json()
        total_count = body["total_count"]
        items.extend(body["items"])
        offset += page_size
        if offset >= total_count:
            break
    return items, total_count, None


async def get_summary(client, headers, date_from, date_to):
    resp = await client.get(
        "/api/v1/analytics/summary",
        headers=headers,
        params={"date_from": date_from, "date_to": date_to},
    )
    if resp.status_code != 200:
        return None, resp
    body = resp.json()
    by_currency = {row["currency"]: row for row in body.get("by_currency", [])}
    return {
        "by_currency": by_currency,
        "day_of_week_expense": body.get("day_of_week_expense", {}),
        "day_of_week_income": body.get("day_of_week_income", {}),
    }, None


async def main() -> None:
    print("Looking up Owner and Member test users...")
    async with async_session_factory() as session:
        owner = await session.scalar(
            select(User).where(User.telegram_id == OWNER_TELEGRAM_ID, User.is_deleted.is_(False))
        )
        member = await session.scalar(
            select(User).where(User.telegram_id == MEMBER_TELEGRAM_ID, User.is_deleted.is_(False))
        )
        if owner is None or member is None:
            print(
                "ERROR: Owner (111111) and/or Member (222222) not found. "
                "Insert test users before running this script."
            )
            sys.exit(1)

        family_budget_id = owner.family_budget_id
        suffix = uuid.uuid4().hex[:6]
        now = datetime.now(UTC)

    owner_headers = auth_header(OWNER_TELEGRAM_ID, "Owner")
    member_headers = auth_header(MEMBER_TELEGRAM_ID, "Member")

    year_from, year_to = default_calendar_year_range(now)
    wide_from = datetime(2000, 1, 1, tzinfo=UTC).isoformat()
    wide_to = datetime(2100, 1, 1, tzinfo=UTC).isoformat()

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        # --- Baseline snapshot, BEFORE inserting this run's data ---
        baseline_summary, err = await get_summary(client, owner_headers, year_from.isoformat(), year_to.isoformat())
        if err is not None:
            print(f"ERROR: baseline summary call failed: {err.text}")
            sys.exit(1)
        _, baseline_total_count, err = await fetch_all_history(client, owner_headers, wide_from, wide_to)
        if err is not None:
            print(f"ERROR: baseline history call failed: {err.text}")
            sys.exit(1)

    # --- Insert this run's test data ---
    async with async_session_factory() as session:
        wallet_uzs = Wallet(family_budget_id=family_budget_id, name=f"Hist-UZS-{suffix}", currency="UZS")
        wallet_usd = Wallet(family_budget_id=family_budget_id, name=f"Hist-USD-{suffix}", currency="USD")
        income_cat = IncomeCategory(family_budget_id=family_budget_id, name=f"Hist-Income-{suffix}")
        expense_top = ExpenseCategory(family_budget_id=family_budget_id, name=f"Hist-Top-{suffix}")
        session.add_all([wallet_uzs, wallet_usd, income_cat, expense_top])
        await session.flush()

        expense_sub_a = ExpenseCategory(
            family_budget_id=family_budget_id, name=f"Hist-SubA-{suffix}", parent_id=expense_top.id
        )
        expense_sub_b = ExpenseCategory(
            family_budget_id=family_budget_id, name=f"Hist-SubB-{suffix}", parent_id=expense_top.id
        )
        session.add_all([expense_sub_a, expense_sub_b])
        await session.flush()

        march_monday = datetime(2026, 3, 2, 10, 0, tzinfo=UTC)  # Monday
        april_wednesday = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)  # Wednesday
        july_thursday = datetime(2026, 7, 16, 15, 0, tzinfo=UTC)

        txns = [
            Transaction(
                family_budget_id=family_budget_id, type="income", wallet_id=wallet_uzs.id, amount=1000,
                income_category_id=income_cat.id, created_by_user_id=owner.id,
                transaction_date=march_monday, comment=f"Income-{suffix}",
            ),
            Transaction(
                family_budget_id=family_budget_id, type="income", wallet_id=wallet_uzs.id, amount=500,
                income_category_id=income_cat.id, created_by_user_id=member.id,
                transaction_date=april_wednesday,
            ),
            Transaction(
                family_budget_id=family_budget_id, type="expense", wallet_id=wallet_uzs.id, amount=300,
                expense_category_id=expense_sub_a.id, created_by_user_id=owner.id,
                transaction_date=march_monday,
            ),
            Transaction(
                family_budget_id=family_budget_id, type="expense", wallet_id=wallet_uzs.id, amount=200,
                expense_category_id=expense_sub_b.id, created_by_user_id=member.id,
                transaction_date=april_wednesday,
            ),
            Transaction(
                family_budget_id=family_budget_id, type="transfer", wallet_id=wallet_uzs.id,
                to_wallet_id=wallet_usd.id, amount=100_000, to_amount=8,
                created_by_user_id=owner.id, transaction_date=july_thursday,
            ),
            Transaction(
                family_budget_id=family_budget_id, type="transfer", wallet_id=wallet_usd.id,
                to_wallet_id=wallet_uzs.id, amount=2, to_amount=25_000,
                created_by_user_id=member.id, transaction_date=july_thursday,
            ),
        ]
        session.add_all(txns)
        await session.commit()
        for t in txns:
            await session.refresh(t)

        created_ids = {str(t.id) for t in txns}
        expense_top_id = expense_top.id
        expense_sub_a_id = expense_sub_a.id
        expense_sub_b_id = expense_sub_b.id
        income_cat_id = income_cat.id

    date_from = datetime(2026, 3, 1, tzinfo=UTC).isoformat()
    date_to = datetime(2026, 7, 31, 23, 59, 59, tzinfo=UTC).isoformat()

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        print("\n=== History: date range required, sorting, membership ===")
        missing = await client.get("/api/v1/transactions/history", headers=owner_headers)
        check("Missing date params -> 422", missing.status_code == 422, missing.text)

        inverted = await client.get(
            "/api/v1/transactions/history",
            headers=owner_headers,
            params={
                "date_from": datetime(2026, 7, 1, tzinfo=UTC).isoformat(),
                "date_to": datetime(2026, 3, 1, tzinfo=UTC).isoformat(),
            },
        )
        check("date_from > date_to -> 422", inverted.status_code == 422, inverted.text)

        all_items, total_count, err = await fetch_all_history(client, owner_headers, wide_from, wide_to)
        check("History fetch -> 200", err is None, err.text if err else "")
        check(
            "total_count increased by exactly 6 vs baseline",
            total_count == baseline_total_count + 6,
            f"baseline={baseline_total_count} after={total_count}",
        )

        by_id = {item["id"]: item for item in all_items}
        our_items = [by_id[i] for i in created_ids if i in by_id]
        check("all 6 created transactions present in history", len(our_items) == 6, str(created_ids - by_id.keys()))

        dates = [item["transaction_date"] for item in all_items]
        check("sorted transaction_date DESC", dates == sorted(dates, reverse=True), "")

        page1 = await client.get(
            "/api/v1/transactions/history",
            headers=owner_headers,
            params={"date_from": wide_from, "date_to": wide_to, "limit": 3, "offset": 0},
        )
        page2 = await client.get(
            "/api/v1/transactions/history",
            headers=owner_headers,
            params={"date_from": wide_from, "date_to": wide_to, "limit": 3, "offset": 3},
        )
        p1_items = page1.json().get("items", []) if page1.status_code == 200 else []
        p2_items = page2.json().get("items", []) if page2.status_code == 200 else []
        check("page 1 has 3 items", len(p1_items) == 3, str(page1.text))
        check("page 2 has 3 items", len(p2_items) == 3, str(page2.text))
        check(
            "pages 1+2 match the first 6 of the full sorted list",
            [i["id"] for i in p1_items] + [i["id"] for i in p2_items] == [i["id"] for i in all_items[:6]],
            "",
        )

        print("\n=== History: created_by for multi-user family ===")
        check(
            "created_by present on all 6 created items",
            all("created_by" in item and item["created_by"] for item in our_items),
            str(our_items[:1]),
        )

        print("\n=== Analytics: expenses top-level rollup (filtered by our own category id) ===")
        exp_cat = await client.get(
            "/api/v1/analytics/expenses-by-category",
            headers=owner_headers,
            params={"date_from": date_from, "date_to": date_to},
        )
        check("expenses-by-category -> 200", exp_cat.status_code == 200, exp_cat.text)
        exp_rows = {row["category_id"]: row for row in exp_cat.json()} if exp_cat.status_code == 200 else {}
        our_top_row = exp_rows.get(str(expense_top_id))
        check(
            "our top-level category rolls up 300+200 = 500",
            our_top_row is not None and our_top_row["amount"] == 500,
            str(our_top_row),
        )

        print("\n=== Analytics: expenses subcategory drill-down ===")
        exp_sub = await client.get(
            "/api/v1/analytics/expenses-by-subcategory",
            headers=owner_headers,
            params={"parent_category_id": str(expense_top_id), "date_from": date_from, "date_to": date_to},
        )
        check("expenses-by-subcategory -> 200", exp_sub.status_code == 200, exp_sub.text)
        sub_rows = {row["subcategory_id"]: row["amount"] for row in exp_sub.json()} if exp_sub.status_code == 200 else {}
        check("sub A amount 300", sub_rows.get(str(expense_sub_a_id)) == 300, str(sub_rows))
        check("sub B amount 200", sub_rows.get(str(expense_sub_b_id)) == 200, str(sub_rows))

        bad_parent = await client.get(
            "/api/v1/analytics/expenses-by-subcategory",
            headers=owner_headers,
            params={"parent_category_id": str(expense_sub_a_id)},
        )
        check("subcategory as parent -> 404", bad_parent.status_code == 404, bad_parent.text)

        print("\n=== Analytics: income by category (filtered by our own category id) ===")
        inc_cat = await client.get(
            "/api/v1/analytics/income-by-category",
            headers=owner_headers,
            params={"date_from": date_from, "date_to": date_to},
        )
        check("income-by-category -> 200", inc_cat.status_code == 200, inc_cat.text)
        inc_rows = {row["category_id"]: row for row in inc_cat.json()} if inc_cat.status_code == 200 else {}
        our_income_row = inc_rows.get(str(income_cat_id))
        check("our income category totals 1500", our_income_row is not None and our_income_row["amount"] == 1500, str(our_income_row))

        print("\n=== Analytics: trend ignores date params ===")
        trend = await client.get(
            "/api/v1/analytics/trend",
            headers=owner_headers,
            params={
                "date_from": datetime(2020, 1, 1, tzinfo=UTC).isoformat(),
                "date_to": datetime(2020, 12, 31, tzinfo=UTC).isoformat(),
            },
        )
        check("trend -> 200", trend.status_code == 200, trend.text)
        trend_rows = trend.json() if trend.status_code == 200 else []
        march = [r for r in trend_rows if r["month"] == "2026-03" and r["currency"] == "UZS"]
        check("trend includes March 2026 UZS row", len(march) == 1, str(march))

        print("\n=== Analytics: summary transfer_net, avg daily, day-of-week (delta vs baseline) ===")
        after_summary, err = await get_summary(client, owner_headers, year_from.isoformat(), year_to.isoformat())
        check("summary -> 200", err is None, err.text if err else "")

        base_uzs = baseline_summary["by_currency"].get("UZS", {})
        after_uzs = after_summary["by_currency"].get("UZS", {}) if after_summary else {}
        base_usd = baseline_summary["by_currency"].get("USD", {})
        after_usd = after_summary["by_currency"].get("USD", {}) if after_summary else {}

        check(
            "UZS transfer_net delta = -100000 + 25000",
            (after_uzs.get("transfer_net", 0) - base_uzs.get("transfer_net", 0)) == -75_000,
            f"before={base_uzs} after={after_uzs}",
        )
        check(
            "USD transfer_net delta = 8 - 2",
            (after_usd.get("transfer_net", 0) - base_usd.get("transfer_net", 0)) == 6,
            f"before={base_usd} after={after_usd}",
        )
        check(
            "UZS income delta = 1500",
            (after_uzs.get("income", 0) - base_uzs.get("income", 0)) == 1500,
            f"before={base_uzs} after={after_uzs}",
        )
        check(
            "UZS expense delta = 500",
            (after_uzs.get("expense", 0) - base_uzs.get("expense", 0)) == 500,
            f"before={base_uzs} after={after_uzs}",
        )

        elapsed = elapsed_days_in_period(year_from, year_to, now)
        expected_avg_after = (base_uzs.get("expense", 0) + 500) / elapsed
        check(
            "average_daily_expense uses elapsed days (within rounding tolerance)",
            close_enough(after_uzs.get("average_daily_expense", -999), expected_avg_after),
            f"elapsed={elapsed} expected~={expected_avg_after:.2f} actual={after_uzs.get('average_daily_expense')}",
        )

        base_exp_dow = baseline_summary["day_of_week_expense"].get("UZS", [0] * 7)
        after_exp_dow = after_summary["day_of_week_expense"].get("UZS", [0] * 7) if after_summary else [0] * 7
        base_inc_dow = baseline_summary["day_of_week_income"].get("UZS", [0] * 7)
        after_inc_dow = after_summary["day_of_week_income"].get("UZS", [0] * 7) if after_summary else [0] * 7

        exp_delta = [a - b for a, b in zip(after_exp_dow, base_exp_dow)]
        inc_delta = [a - b for a, b in zip(after_inc_dow, base_inc_dow)]
        check(
            "day_of_week expense delta: Mon +300, Wed +200, rest 0",
            exp_delta == [300, 0, 200, 0, 0, 0, 0],
            str(exp_delta),
        )
        check(
            "day_of_week income delta: Mon +1000, Wed +500, rest 0",
            inc_delta == [1000, 0, 500, 0, 0, 0, 0],
            str(inc_delta),
        )

        print("\n=== Member read access (no 403) ===")
        for path, params in [
            ("/api/v1/transactions/history", {"date_from": date_from, "date_to": date_to}),
            ("/api/v1/analytics/expenses-by-category", {"date_from": date_from, "date_to": date_to}),
            (
                "/api/v1/analytics/expenses-by-subcategory",
                {"parent_category_id": str(expense_top_id), "date_from": date_from, "date_to": date_to},
            ),
            ("/api/v1/analytics/income-by-category", {"date_from": date_from, "date_to": date_to}),
            ("/api/v1/analytics/trend", {}),
            ("/api/v1/analytics/summary", {"date_from": year_from.isoformat(), "date_to": year_to.isoformat()}),
        ]:
            resp = await client.get(path, headers=member_headers, params=params)
            check(f"Member GET {path} -> 200", resp.status_code == 200, resp.text)

        print("\n=== Analytics default calendar year when dates omitted ===")
        default_inc = await client.get("/api/v1/analytics/income-by-category", headers=owner_headers)
        check("default income-by-category -> 200", default_inc.status_code == 200, default_inc.text)
        default_rows = {row["category_id"]: row for row in default_inc.json()} if default_inc.status_code == 200 else {}
        default_row = default_rows.get(str(income_cat_id))
        check(
            "default range (no dates) includes our income category, amount 1500",
            default_row is not None and default_row["amount"] == 1500,
            str(default_row),
        )

    print(f"\n===== SUMMARY: {passed} passed, {failed} failed =====")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())