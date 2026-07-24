"""
Verification script for Task 16 — backend query/index optimization.

Run from backend/ directory, venv activated, `docker compose up -d postgres`,
and the FastAPI dev server running locally on http://localhost:8000:

    python -m scripts.manual_verify_task16_optimization

Uses an isolated throwaway family (not the shared 111111/222222 fixture),
created directly via async_session_factory — this is additive test data,
not destructive, but kept isolated to avoid polluting the shared fixture's
counts.

Checks:
1. Postgres session timezone — guards the date_trunc() TZ risk flagged
   during code review of get_trend().
2. Trend month-bucket correctness at an exact month boundary (00:00:00 UTC
   on the 1st vs 23:59:59 UTC the day before) — the real behavioral test;
   passes regardless of #1 as long as bucketing is actually correct.
3. transaction_count parity between the new aggregate list endpoints
   (GET /wallets, /categories/income, /categories/expense) and the
   existing single-item count path (still exercised via PATCH response) —
   confirms the N+1 fix didn't change the numbers returned.
4. EXPLAIN spot-check that the new indexes exist and are chosen by the
   query planner. NOTE: on a small/dev-sized table Postgres may prefer a
   sequential scan regardless of the index (this is normal, not a bug) —
   this check is informational and does not fail the run.
"""
import asyncio
import sys
import time
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import text

from app.db import async_session_factory
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from scripts.gen_test_initdata import build_init_data

BASE_URL = "http://localhost:8000"
results: list[tuple[str, bool, str]] = []
info: list[str] = []


def auth_headers(telegram_id: int) -> dict[str, str]:
    init_data = build_init_data(
        telegram_id,
        "Test",
        "",
        "verify_task16",
        "ru",
        int(time.time()),
    )
    return {"Authorization": f"tma {init_data}"}


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, condition, detail))
    status = "[PASS]" if condition else "[FAIL]"
    print(f"{status} {name}" + (f" — {detail}" if detail and not condition else ""))


async def setup_family() -> tuple[uuid.UUID, uuid.UUID, int]:
    telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    async with async_session_factory() as session:
        budget = FamilyBudget(invite_token=f"verify-task16-{uuid.uuid4()}")
        session.add(budget)
        await session.flush()
        user = User(
            telegram_id=telegram_id,
            family_budget_id=budget.id,
            role="owner",
            language="ru",
        )
        session.add(user)
        await session.flush()
        await session.commit()
        return budget.id, user.id, telegram_id


async def check_timezone() -> None:
    async with async_session_factory() as session:
        tz = (await session.execute(text("SHOW timezone"))).scalar_one()
    check(
        "Postgres session timezone is UTC",
        tz.upper() in ("UTC", "ETC/UTC"),
        f"actual: {tz!r} — get_trend()'s date_trunc() buckets by this "
        "timezone, not automatically UTC. If not UTC in production, either "
        "set it explicitly on the connection or switch to "
        "date_trunc('month', transaction_date AT TIME ZONE 'UTC').",
    )


async def check_trend_month_boundaries(
    client: httpx.AsyncClient, budget_id: uuid.UUID, user_id: uuid.UUID, telegram_id: int
) -> None:
    async with async_session_factory() as session:
        wallet = Wallet(family_budget_id=budget_id, name="V", currency="UZS")
        income_cat = IncomeCategory(family_budget_id=budget_id, name="V")
        session.add_all([wallet, income_cat])
        await session.flush()

        month_start_txn = Transaction(
            family_budget_id=budget_id,
            type="income",
            wallet_id=wallet.id,
            amount=111,
            income_category_id=income_cat.id,
            created_by_user_id=user_id,
            transaction_date=datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc),
        )
        prev_month_txn = Transaction(
            family_budget_id=budget_id,
            type="income",
            wallet_id=wallet.id,
            amount=222,
            income_category_id=income_cat.id,
            created_by_user_id=user_id,
            transaction_date=datetime(2026, 5, 31, 23, 59, 59, tzinfo=timezone.utc),
        )
        session.add_all([month_start_txn, prev_month_txn])
        await session.commit()

    headers = auth_headers(telegram_id)
    resp = await client.get(f"{BASE_URL}/api/v1/analytics/trend", headers=headers)
    entries = resp.json()

    june = next((e for e in entries if e["month"] == "2026-06" and e["currency"] == "UZS"), None)
    may = next((e for e in entries if e["month"] == "2026-05" and e["currency"] == "UZS"), None)

    check(
        "Trend: transaction at 2026-06-01T00:00:00Z lands in June bucket",
        june is not None and june["income"] == 111,
        f"june entry: {june}",
    )
    check(
        "Trend: transaction at 2026-05-31T23:59:59Z lands in May bucket, not June",
        may is not None and may["income"] == 222 and (june is None or june["income"] == 111),
        f"may entry: {may}, june entry: {june}",
    )


async def check_count_parity(
    client: httpx.AsyncClient, budget_id: uuid.UUID, user_id: uuid.UUID, telegram_id: int
) -> None:
    headers = auth_headers(telegram_id)

    async with async_session_factory() as session:
        wallet_a = Wallet(family_budget_id=budget_id, name="A", currency="UZS")
        wallet_b = Wallet(family_budget_id=budget_id, name="B", currency="UZS")
        income_cat = IncomeCategory(family_budget_id=budget_id, name="Parity income")
        expense_top = ExpenseCategory(family_budget_id=budget_id, name="Parity expense top")
        session.add_all([wallet_a, wallet_b, income_cat, expense_top])
        await session.flush()
        expense_sub = ExpenseCategory(
            family_budget_id=budget_id, name="Parity expense sub", parent_id=expense_top.id
        )
        session.add(expense_sub)
        await session.flush()

        now = datetime.now(timezone.utc)
        session.add_all(
            [
                # wallet_a: source for income, source for expense, destination
                # for transfer -> count 3
                Transaction(
                    family_budget_id=budget_id, type="income", wallet_id=wallet_a.id,
                    amount=100, income_category_id=income_cat.id,
                    created_by_user_id=user_id, transaction_date=now,
                ),
                Transaction(
                    family_budget_id=budget_id, type="transfer", wallet_id=wallet_b.id,
                    to_wallet_id=wallet_a.id, amount=50, to_amount=50,
                    created_by_user_id=user_id, transaction_date=now,
                ),
                Transaction(
                    family_budget_id=budget_id, type="expense", wallet_id=wallet_a.id,
                    amount=30, expense_category_id=expense_sub.id,
                    created_by_user_id=user_id, transaction_date=now,
                ),
            ]
        )
        await session.commit()

    wallets_list = (await client.get(f"{BASE_URL}/api/v1/wallets", headers=headers)).json()
    income_list = (await client.get(f"{BASE_URL}/api/v1/categories/income", headers=headers)).json()
    expense_list = (await client.get(f"{BASE_URL}/api/v1/categories/expense", headers=headers)).json()

    wallet_a_list_count = next(w["transaction_count"] for w in wallets_list if w["name"] == "A")
    income_list_count = next(c["transaction_count"] for c in income_list if c["name"] == "Parity income")
    expense_sub_list_count = next(
        c["transaction_count"] for c in expense_list if c["name"] == "Parity expense sub"
    )

    wallet_a_id = next(w["id"] for w in wallets_list if w["name"] == "A")
    income_id = next(c["id"] for c in income_list if c["name"] == "Parity income")
    expense_sub_id = next(c["id"] for c in expense_list if c["name"] == "Parity expense sub")

    # PATCH still exercises the old single-item count_*_transactions() path.
    wallet_a_patch = (
        await client.patch(
            f"{BASE_URL}/api/v1/wallets/{wallet_a_id}", headers=headers, json={"name": "A"}
        )
    ).json()
    income_patch = (
        await client.patch(
            f"{BASE_URL}/api/v1/categories/income/{income_id}",
            headers=headers, json={"name": "Parity income"},
        )
    ).json()
    expense_sub_patch = (
        await client.patch(
            f"{BASE_URL}/api/v1/categories/expense/{expense_sub_id}",
            headers=headers, json={"name": "Parity expense sub"},
        )
    ).json()

    check(
        "Wallet transaction_count matches: list-aggregate vs single-item path",
        wallet_a_list_count == wallet_a_patch["transaction_count"] == 3,
        f"list={wallet_a_list_count}, single-item={wallet_a_patch['transaction_count']}, expected=3",
    )
    check(
        "Income category transaction_count matches: list-aggregate vs single-item path",
        income_list_count == income_patch["transaction_count"] == 1,
        f"list={income_list_count}, single-item={income_patch['transaction_count']}, expected=1",
    )
    check(
        "Expense subcategory transaction_count matches: list-aggregate vs single-item path",
        expense_sub_list_count == expense_sub_patch["transaction_count"] == 1,
        f"list={expense_sub_list_count}, single-item={expense_sub_patch['transaction_count']}, expected=1",
    )


async def check_indexes_used() -> None:
    queries = {
        "ix_transactions_wallet_id_active": (
            "SELECT 1 FROM transactions "
            "WHERE wallet_id = '00000000-0000-0000-0000-000000000000' "
            "AND is_deleted = false"
        ),
        "ix_transactions_family_date_id_active": (
            "SELECT 1 FROM transactions "
            "WHERE family_budget_id = '00000000-0000-0000-0000-000000000000' "
            "AND is_deleted = false "
            "ORDER BY transaction_date DESC, id DESC LIMIT 20"
        ),
    }
    async with async_session_factory() as session:
        for index_name, query in queries.items():
            plan_rows = (await session.execute(text(f"EXPLAIN {query}"))).scalars().all()
            plan_text = "\n".join(plan_rows)
            used = index_name in plan_text or "Index" in plan_text
            info.append(
                f"[INFO] {index_name}: {'used' if used else 'NOT used (likely small table — recheck on prod-like data)'}"
            )


async def main() -> None:
    await check_timezone()

    budget_id, user_id, telegram_id = await setup_family()

    async with httpx.AsyncClient() as client:
        await check_trend_month_boundaries(client, budget_id, user_id, telegram_id)
        await check_count_parity(client, budget_id, user_id, telegram_id)

    await check_indexes_used()

    print()
    for line in info:
        print(line)

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} PASS")
    if failed:
        print("FAILED:")
        for name, _, detail in failed:
            print(f"  - {name}: {detail}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
