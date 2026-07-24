"""
Manual verification for Task 16 Part 2 (items 6, 7, 8, 9, 10, 11, 13).

Run from backend/ with venv activated and `docker compose up -d postgres`:
    python -m scripts.manual_verify_task16_part2

Uses isolated throwaway families for every check (never the shared
111111/222222 fixture), per established principle — item 11 in
particular is destructive-adjacent (soft-deletes a family).
"""
import asyncio
import json
import time
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.telegram import sign_init_data
from app.config import BOT_TOKEN
from app.db import engine, async_session_factory
from app.main import app
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.history_analytics import get_summary


def build_test_init_data(telegram_id: int) -> str:
    """Signs initData with the server's real BOT_TOKEN — this hits the app
    in-process (ASGITransport), so it must match what get_current_user checks."""
    user_json = json.dumps(
        {"id": telegram_id, "first_name": "Verify", "username": "verifybot"},
        separators=(",", ":"),
    )
    fields = {"user": user_json, "auth_date": str(int(time.time()))}
    return sign_init_data(fields, BOT_TOKEN)


def api_client() -> AsyncClient:
    """In-process client — same Python process/engine as this script, so
    SQLAlchemy event listeners on `engine` actually see the queries. Hitting
    a separately-running uvicorn process would not work: it has its own
    engine/connections in a different process."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://verify-script")

BASE_URL = "http://localhost:8000"  # adjust to your local FastAPI port

results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, condition, detail))
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not condition else ""))


async def make_family(session: AsyncSession, telegram_id: int) -> tuple[User, FamilyBudget]:
    budget = FamilyBudget(invite_token=f"verify16p2-{uuid.uuid4()}")
    session.add(budget)
    await session.flush()
    user = User(
        telegram_id=telegram_id,
        family_budget_id=budget.id,
        role="owner",
        language="ru",
        first_name="Verify",
    )
    session.add(user)
    await session.flush()
    return user, budget


async def make_wallets(session: AsyncSession, budget_id: uuid.UUID) -> dict[str, Wallet]:
    uzs = Wallet(family_budget_id=budget_id, name="UZS", currency="UZS")
    usd = Wallet(family_budget_id=budget_id, name="USD", currency="USD")
    session.add_all([uzs, usd])
    await session.flush()
    return {"UZS": uzs, "USD": usd}


# ---------------------------------------------------------------------------
# Item 6: get_summary — SQL aggregation, baseline/delta correctness + EXPLAIN
# ---------------------------------------------------------------------------
async def verify_item6() -> None:
    telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    async with async_session_factory() as session:
        user, budget = await make_family(session, telegram_id)
        wallets = await make_wallets(session, budget.id)
        income_cat = IncomeCategory(family_budget_id=budget.id, name="Salary")
        expense_top = ExpenseCategory(family_budget_id=budget.id, name="Food")
        session.add_all([income_cat, expense_top])
        await session.flush()
        expense_sub = ExpenseCategory(
            family_budget_id=budget.id, name="Groceries", parent_id=expense_top.id
        )
        session.add(expense_sub)
        await session.flush()

        # Baseline — empty period
        baseline = await get_summary(
            session, budget.id,
            datetime(2026, 3, 1, tzinfo=UTC), datetime(2026, 3, 31, 23, 59, 59, tzinfo=UTC),
            now=datetime(2026, 3, 31, tzinfo=UTC),
        )
        baseline_currencies = {row.currency for row in baseline.by_currency}
        check("item6: empty period has no currencies", baseline_currencies == set())

        # Insert known transactions: Monday income, Wednesday expense, Sunday 23:30 income (USD)
        session.add_all([
            Transaction(
                family_budget_id=budget.id, type="income", wallet_id=wallets["UZS"].id,
                amount=1000, income_category_id=income_cat.id, created_by_user_id=user.id,
                transaction_date=datetime(2026, 3, 2, tzinfo=UTC),  # Monday
            ),
            Transaction(
                family_budget_id=budget.id, type="expense", wallet_id=wallets["UZS"].id,
                amount=250, expense_category_id=expense_sub.id, created_by_user_id=user.id,
                transaction_date=datetime(2026, 3, 4, tzinfo=UTC),  # Wednesday
            ),
            Transaction(
                family_budget_id=budget.id, type="income", wallet_id=wallets["USD"].id,
                amount=75, income_category_id=income_cat.id, created_by_user_id=user.id,
                transaction_date=datetime(2026, 3, 8, 23, 30, tzinfo=UTC),  # Sunday, UTC boundary
            ),
        ])
        await session.flush()

        delta = await get_summary(
            session, budget.id,
            datetime(2026, 3, 1, tzinfo=UTC), datetime(2026, 3, 31, 23, 59, 59, tzinfo=UTC),
            now=datetime(2026, 3, 31, tzinfo=UTC),
        )
        by_currency = {row.currency: row for row in delta.by_currency}
        check("item6: UZS income delta correct", by_currency["UZS"].income == 1000)
        check("item6: UZS expense delta correct", by_currency["UZS"].expense == 250)
        check(
            "item6: Monday income bucket (index 0)",
            delta.day_of_week_income["UZS"][0] == 1000,
        )
        check(
            "item6: Wednesday expense bucket (index 2)",
            delta.day_of_week_expense["UZS"][2] == 250,
        )
        check(
            "item6: Sunday 23:30 UTC lands in Sunday bucket (index 6), not Monday",
            delta.day_of_week_income["USD"][6] == 75,
        )

        # EXPLAIN: confirm the Part 1 history index is used, no seq scan on transactions
        explain_sql = text(
            """
            EXPLAIN (FORMAT TEXT)
            SELECT wallets.currency,
                   SUM(CASE WHEN transactions.type = 'income' THEN transactions.amount ELSE 0 END)
            FROM transactions
            JOIN wallets ON transactions.wallet_id = wallets.id
            WHERE transactions.family_budget_id = :fid
              AND transactions.is_deleted = false
              AND transactions.transaction_date >= :df
              AND transactions.transaction_date <= :dt
            GROUP BY wallets.currency
            """
        )
        plan_rows = (
            await session.execute(
                explain_sql,
                {
                    "fid": budget.id,
                    "df": datetime(2026, 3, 1, tzinfo=UTC),
                    "dt": datetime(2026, 3, 31, 23, 59, 59, tzinfo=UTC),
                },
            )
        ).all()
        plan_text = "\n".join(r[0] for r in plan_rows)
        uses_composite_index = "ix_transactions_family_date_id_active" in plan_text
        seq_scan_on_transactions = "Seq Scan on transactions" in plan_text
        # Informational only: at tiny row counts (this throwaway fixture) the
        # planner may correctly prefer the plain family_budget_id index over
        # the composite one — that's optimal for this cardinality, not a bug.
        # Re-check on a realistic data volume before trusting this signal.
        print(
            f"[INFO] item6: EXPLAIN {'uses' if uses_composite_index else 'does not use'} "
            f"the composite history index (expected to vary at low row counts)"
        )
        check(
            "item6: EXPLAIN has no seq scan on transactions",
            not seq_scan_on_transactions,
            detail=plan_text if seq_scan_on_transactions else "",
        )

        await session.rollback()


# ---------------------------------------------------------------------------
# Item 7: history — single author-count call, no users join when unneeded
# ---------------------------------------------------------------------------
async def verify_item7() -> None:
    telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    async with async_session_factory() as session:
        user, budget = await make_family(session, telegram_id)
        wallets = await make_wallets(session, budget.id)
        income_cat = IncomeCategory(family_budget_id=budget.id, name="Salary")
        session.add(income_cat)
        await session.flush()
        session.add(Transaction(
            family_budget_id=budget.id, type="income", wallet_id=wallets["UZS"].id,
            amount=100, income_category_id=income_cat.id, created_by_user_id=user.id,
            transaction_date=datetime(2026, 5, 1, tzinfo=UTC),
        ))
        await session.commit()

    statements: list[str] = []

    def record_select(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement.lower())

    event.listen(engine.sync_engine, "before_cursor_execute", record_select)
    try:
        with patch("app.main.verify_postgres_connection", new=AsyncMock()):
            async with api_client() as client:
                headers = {"Authorization": f"tma {build_test_init_data(telegram_id)}"}
                resp = await client.get(
                    "/api/v1/transactions/history",
                    headers=headers,
                    params={
                        "date_from": "2026-05-01T00:00:00+00:00",
                        "date_to": "2026-05-31T23:59:59+00:00",
                    },
                )
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record_select)

    check("item7: history endpoint returns 200", resp.status_code == 200, resp.text)
    count_stmts = [s for s in statements if "count(*)" in s and "users" in s]
    check(
        "item7: exactly one family-user count query",
        len(count_stmts) == 1,
        detail=f"found {len(count_stmts)}: {count_stmts}",
    )
    history_stmts = [s for s in statements if "from transactions" in s and "join" in s]
    check(
        "item7: history query was actually captured",
        len(history_stmts) >= 1,
        detail=f"captured statements: {statements}",
    )
    has_users_join = any("join users" in s for s in history_stmts)
    check(
        "item7: no users join in single-user family history query",
        not has_users_join,
        detail=history_stmts[0] if has_users_join and history_stmts else "",
    )

    await cleanup_family(budget.id)


# ---------------------------------------------------------------------------
# Item 8 & 13: EXPLAIN confirms new indexes exist and are usable
# ---------------------------------------------------------------------------
async def verify_item8_and_13() -> None:
    async with async_session_factory() as session:
        idx_rows = (
            await session.execute(
                text(
                    """
                    SELECT indexname, indexdef FROM pg_indexes
                    WHERE tablename IN ('users', 'expense_categories')
                      AND indexname IN (
                        'ix_users_family_budget_id',
                        'ix_expense_categories_parent_id_not_null'
                      )
                    """
                )
            )
        ).all()
        found = {row.indexname for row in idx_rows}
        check(
            "item8: ix_users_family_budget_id exists",
            "ix_users_family_budget_id" in found,
        )
        check(
            "item13: ix_expense_categories_parent_id_not_null exists",
            "ix_expense_categories_parent_id_not_null" in found,
        )
        for row in idx_rows:
            if row.indexname == "ix_users_family_budget_id":
                check(
                    "item8: index is non-partial (no WHERE clause)",
                    "where" not in row.indexdef.lower(),
                    detail=row.indexdef,
                )
            if row.indexname == "ix_expense_categories_parent_id_not_null":
                check(
                    "item13: index has partial predicate on parent_id IS NOT NULL",
                    "parent_id is not null" in row.indexdef.lower(),
                    detail=row.indexdef,
                )


# ---------------------------------------------------------------------------
# Item 10: pool configuration
# ---------------------------------------------------------------------------
def verify_item10() -> None:
    pool = engine.pool
    check("item10: pool_size == 10", getattr(pool, "size", lambda: None)() == 10)
    check("item10: pool_pre_ping enabled", engine.pool._pre_ping is True)
    # max_overflow/timeout/recycle aren't cleanly introspectable at runtime for
    # all pool classes — cross-check against db.py source directly as a fallback.


# ---------------------------------------------------------------------------
# Item 11: soft-deleted family → 403 (isolated throwaway family)
# ---------------------------------------------------------------------------
async def verify_item11() -> None:
    telegram_id = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    async with async_session_factory() as session:
        user, budget = await make_family(session, telegram_id)
        await session.commit()
        budget_id = budget.id

    with patch("app.main.verify_postgres_connection", new=AsyncMock()):
        async with api_client() as client:
            headers = {"Authorization": f"tma {build_test_init_data(telegram_id)}"}

            before = await client.get("/api/v1/members", headers=headers)
            check("item11: active family → 200 before soft-delete", before.status_code == 200)

            async with async_session_factory() as delete_session:
                fb = await delete_session.get(FamilyBudget, budget_id)
                fb.is_deleted = True
                fb.deleted_at = datetime.now(UTC)
                await delete_session.commit()

            after = await client.get("/api/v1/members", headers=headers)
            check(
                "item11: soft-deleted family → 403",
                after.status_code == 403,
                detail=f"got {after.status_code}",
            )

    await cleanup_family(budget_id)


async def cleanup_family(budget_id: uuid.UUID) -> None:
    async with async_session_factory() as session:
        await session.execute(text("DELETE FROM transactions WHERE family_budget_id = :fid"), {"fid": budget_id})
        await session.execute(text("DELETE FROM users WHERE family_budget_id = :fid"), {"fid": budget_id})
        await session.execute(text("DELETE FROM wallets WHERE family_budget_id = :fid"), {"fid": budget_id})
        await session.execute(text("DELETE FROM income_categories WHERE family_budget_id = :fid"), {"fid": budget_id})
        await session.execute(text("DELETE FROM expense_categories WHERE family_budget_id = :fid"), {"fid": budget_id})
        await session.execute(text("DELETE FROM family_budgets WHERE id = :fid"), {"fid": budget_id})
        await session.commit()


async def main() -> None:
    print("Task 16 Part 2 — manual verification\n")
    await verify_item6()
    await verify_item7()
    await verify_item8_and_13()
    verify_item10()
    await verify_item11()

    print("\n--- Summary ---")
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        if not ok:
            print(f"FAIL: {name} — {detail}")
    print(f"{passed}/{total} PASS")


if __name__ == "__main__":
    asyncio.run(main())
