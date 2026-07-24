"""
Manual verification script for the currency-scoping fix on:
  - GET /api/v1/analytics/expenses-by-category
  - GET /api/v1/analytics/expenses-by-subcategory
  - GET /api/v1/analytics/income-by-category

Run from backend/ as a module, with the server already running locally:
    python -m scripts.manual_verify_currency_scoping

Follows the same conventions as manual_verify_history_analytics.py:
  - looks up the existing test Owner (telegram_id=111111) and Member
    (telegram_id=222222) by telegram_id, does not create new users
  - creates its own wallets/categories with a unique suffix per run
  - inserts its own transactions directly via async_session_factory
  - compares against category ids created in THIS run only (unique
    suffix), so no baseline/delta snapshot is needed for correctness —
    but the test data is deliberately designed to reproduce exactly
    the bug scenario: one category with transactions in both UZS and
    USD, to confirm they are no longer summed together
  - exercises the endpoints via httpx against the running server
  - prints [PASS]/[FAIL] per acceptance-criteria item, exit code 1 on
    any failure
"""

import asyncio
import sys
import uuid
from datetime import datetime, timezone

import httpx

from app.db import async_session_factory
from app.models.user import User
from app.models.wallet import Wallet
from app.models.income_category import IncomeCategory
from app.models.expense_category import ExpenseCategory
from app.models.transaction import Transaction
from scripts.gen_test_initdata import build_init_data

from sqlalchemy import select

BASE_URL = "http://127.0.0.1:8000"
OWNER_TG_ID = 111111
RUN_SUFFIX = uuid.uuid4().hex[:8]

results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, condition, detail))
    status = "[PASS]" if condition else "[FAIL]"
    print(f"{status} {name}" + (f" — {detail}" if detail and not condition else ""))


async def get_owner(session):
    result = await session.execute(select(User).where(User.telegram_id == OWNER_TG_ID))
    owner = result.scalar_one_or_none()
    if owner is None:
        print(f"ERROR: test Owner with telegram_id={OWNER_TG_ID} not found. "
              f"Run earlier task setup first.")
        sys.exit(1)
    return owner


async def setup_data():
    """Create isolated wallets/categories/transactions for this run only."""
    async with async_session_factory() as session:
        owner = await get_owner(session)
        family_budget_id = owner.family_budget_id

        wallet_uzs = Wallet(
            id=uuid.uuid4(),
            family_budget_id=family_budget_id,
            name=f"CurTest UZS {RUN_SUFFIX}",
            currency="UZS",
        )
        wallet_usd = Wallet(
            id=uuid.uuid4(),
            family_budget_id=family_budget_id,
            name=f"CurTest USD {RUN_SUFFIX}",
            currency="USD",
        )
        session.add_all([wallet_uzs, wallet_usd])

        income_cat = IncomeCategory(
            id=uuid.uuid4(),
            family_budget_id=family_budget_id,
            name=f"CurTest Income {RUN_SUFFIX}",
        )
        expense_parent = ExpenseCategory(
            id=uuid.uuid4(),
            family_budget_id=family_budget_id,
            name=f"CurTest Expense Parent {RUN_SUFFIX}",
            parent_id=None,
        )
        session.add_all([income_cat, expense_parent])
        await session.flush()

        expense_sub = ExpenseCategory(
            id=uuid.uuid4(),
            family_budget_id=family_budget_id,
            name=f"CurTest Expense Sub {RUN_SUFFIX}",
            parent_id=expense_parent.id,
        )
        session.add(expense_sub)
        await session.flush()

        now = datetime.now(timezone.utc)

        # Same category, both currencies — the exact case that was
        # previously broken (summed together instead of scoped).
        transactions = [
            Transaction(
                id=uuid.uuid4(), family_budget_id=family_budget_id,
                type="income", transaction_date=now, amount=1000,
                wallet_id=wallet_uzs.id, income_category_id=income_cat.id,
                created_by_user_id=owner.id,
            ),
            Transaction(
                id=uuid.uuid4(), family_budget_id=family_budget_id,
                type="income", transaction_date=now, amount=25,
                wallet_id=wallet_usd.id, income_category_id=income_cat.id,
                created_by_user_id=owner.id,
            ),
            Transaction(
                id=uuid.uuid4(), family_budget_id=family_budget_id,
                type="expense", transaction_date=now, amount=300,
                wallet_id=wallet_uzs.id, expense_category_id=expense_sub.id,
                created_by_user_id=owner.id,
            ),
            Transaction(
                id=uuid.uuid4(), family_budget_id=family_budget_id,
                type="expense", transaction_date=now, amount=50,
                wallet_id=wallet_usd.id, expense_category_id=expense_sub.id,
                created_by_user_id=owner.id,
            ),
        ]
        session.add_all(transactions)
        await session.commit()

        return {
            "family_budget_id": family_budget_id,
            "wallet_uzs": wallet_uzs.id,
            "wallet_usd": wallet_usd.id,
            "income_cat": income_cat.id,
            "expense_parent": expense_parent.id,
            "expense_sub": expense_sub.id,
        }


def find_amount(items: list, cat_id: str) -> float:
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("id") == cat_id or item.get("category_id") == cat_id or item.get("subcategory_id") == cat_id:
            return item.get("amount", 0)
    return 0


def extract_items(payload):
    if isinstance(payload, dict):
        return payload.get("items", [])
    return payload


async def main():
    ids = await setup_data()

    init_data = build_init_data(
        telegram_id=OWNER_TG_ID, first_name="Test", last_name="Owner",
        username="test_owner", language_code="ru",
        auth_date=int(datetime.now(timezone.utc).timestamp()),
    )
    headers = {"Authorization": f"tma {init_data}"}

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:

        # --- 1. Missing currency param -> 422 on all three endpoints ---
        r1 = await client.get("/api/v1/analytics/expenses-by-category", headers=headers)
        check("expenses-by-category: 422 when currency missing", r1.status_code == 422,
              f"got {r1.status_code}")

        r2 = await client.get(
            "/api/v1/analytics/expenses-by-subcategory",
            params={"parent_category_id": str(ids["expense_parent"])},
            headers=headers,
        )
        check("expenses-by-subcategory: 422 when currency missing", r2.status_code == 422,
              f"got {r2.status_code}")

        r3 = await client.get("/api/v1/analytics/income-by-category", headers=headers)
        check("income-by-category: 422 when currency missing", r3.status_code == 422,
              f"got {r3.status_code}")

        # --- 2. Invalid currency value -> 422 ---
        r4 = await client.get(
            "/api/v1/analytics/expenses-by-category",
            params={"currency": "EUR"}, headers=headers,
        )
        check("expenses-by-category: 422 for invalid currency (EUR)", r4.status_code == 422,
              f"got {r4.status_code}")

        # --- 3. expenses-by-category correctly scoped per currency ---
        r_uzs = await client.get(
            "/api/v1/analytics/expenses-by-category",
            params={"currency": "UZS"}, headers=headers,
        )
        r_usd = await client.get(
            "/api/v1/analytics/expenses-by-category",
            params={"currency": "USD"}, headers=headers,
        )
        check("expenses-by-category: 200 for UZS and USD",
              r_uzs.status_code == 200 and r_usd.status_code == 200,
              f"UZS={r_uzs.status_code} USD={r_usd.status_code}")

        if r_uzs.status_code == 200 and r_usd.status_code == 200:
            amt_uzs = find_amount(extract_items(r_uzs.json()), str(ids["expense_parent"]))
            amt_usd = find_amount(extract_items(r_usd.json()), str(ids["expense_parent"]))
            check("expenses-by-category: UZS amount == 300 (not merged with USD)", amt_uzs == 300,
                  f"got {amt_uzs}")
            check("expenses-by-category: USD amount == 50 (not merged with UZS)", amt_usd == 50,
                  f"got {amt_usd}")

        # --- 4. expenses-by-subcategory correctly scoped per currency ---
        r_sub_uzs = await client.get(
            "/api/v1/analytics/expenses-by-subcategory",
            params={"parent_category_id": str(ids["expense_parent"]), "currency": "UZS"},
            headers=headers,
        )
        r_sub_usd = await client.get(
            "/api/v1/analytics/expenses-by-subcategory",
            params={"parent_category_id": str(ids["expense_parent"]), "currency": "USD"},
            headers=headers,
        )
        check("expenses-by-subcategory: 200 for UZS and USD",
              r_sub_uzs.status_code == 200 and r_sub_usd.status_code == 200,
              f"UZS={r_sub_uzs.status_code} USD={r_sub_usd.status_code}")

        if r_sub_uzs.status_code == 200 and r_sub_usd.status_code == 200:
            sub_amt_uzs = find_amount(extract_items(r_sub_uzs.json()), str(ids["expense_sub"]))
            sub_amt_usd = find_amount(extract_items(r_sub_usd.json()), str(ids["expense_sub"]))
            check("expenses-by-subcategory: UZS amount == 300", sub_amt_uzs == 300, f"got {sub_amt_uzs}")
            check("expenses-by-subcategory: USD amount == 50", sub_amt_usd == 50, f"got {sub_amt_usd}")
            if sub_amt_uzs != 300 or sub_amt_usd != 50:
                print("\nDEBUG expenses-by-subcategory raw responses:")
                print("  expected expense_sub id:", ids["expense_sub"])
                print("  UZS response body:", r_sub_uzs.json())
                print("  USD response body:", r_sub_usd.json())

        # --- 5. income-by-category correctly scoped per currency ---
        r_inc_uzs = await client.get(
            "/api/v1/analytics/income-by-category",
            params={"currency": "UZS"}, headers=headers,
        )
        r_inc_usd = await client.get(
            "/api/v1/analytics/income-by-category",
            params={"currency": "USD"}, headers=headers,
        )
        check("income-by-category: 200 for UZS and USD",
              r_inc_uzs.status_code == 200 and r_inc_usd.status_code == 200,
              f"UZS={r_inc_uzs.status_code} USD={r_inc_usd.status_code}")

        if r_inc_uzs.status_code == 200 and r_inc_usd.status_code == 200:
            inc_amt_uzs = find_amount(extract_items(r_inc_uzs.json()), str(ids["income_cat"]))
            inc_amt_usd = find_amount(extract_items(r_inc_usd.json()), str(ids["income_cat"]))
            check("income-by-category: UZS amount == 1000", inc_amt_uzs == 1000, f"got {inc_amt_uzs}")
            check("income-by-category: USD amount == 25", inc_amt_usd == 25, f"got {inc_amt_usd}")

        # --- 6. Response shape unchanged: no per-item currency field added ---
        if r_uzs.status_code == 200:
            items = extract_items(r_uzs.json())
            if items:
                has_currency_field = any(
                    isinstance(item, dict) and "currency" in item for item in items
                )
                check("expenses-by-category: response items have no per-item currency field",
                      not has_currency_field,
                      "found unexpected 'currency' key in item — spec says scoping is via query param only")

    print()
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"Summary: {passed}/{total} passed")
    if passed != total:
        print("\nFAILED CHECKS:")
        for name, ok, detail in results:
            if not ok:
                print(f"  - {name}" + (f" ({detail})" if detail else ""))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
