"""
Automated manual verification of Acceptance criteria in
docs/tasks/08-api-wallet-balances.md.

Prerequisites:
  1. Server running: uvicorn app.main:app --reload (port 8000)
  2. Owner (telegram_id=111111) and Member (telegram_id=222222) exist in DB.

Run (from backend/, with venv active):
    python -m scripts.manual_verify_wallet_balances

Design note: the family's test data is never cleaned between runs (project
convention), so this script never asserts absolute totals for the reused
Owner/Member family — it captures a baseline snapshot before inserting its
own transactions and asserts the delta after insertion. The one exception
is the "zero wallets of a currency -> balance: 0" check, which needs an
absolute zero and therefore uses a brand-new, throwaway family_budget +
user created just for that check (never touched again).
"""

import asyncio
import random
import sys
import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import select

from app.db import async_session_factory
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
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


async def get_balances(client: httpx.AsyncClient, headers: dict[str, str]):
    resp = await client.get("/api/v1/analytics/wallet-balances", headers=headers)
    if resp.status_code != 200:
        return None, resp
    body = resp.json()
    by_currency = {row["currency"]: row["balance"] for row in body.get("balances", [])}
    return {"raw": body, "by_currency": by_currency}, None


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

    owner_headers = auth_header(OWNER_TELEGRAM_ID, "Owner")
    member_headers = auth_header(MEMBER_TELEGRAM_ID, "Member")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        # --- Baseline snapshot, BEFORE inserting this run's data ---
        baseline, err = await get_balances(client, owner_headers)
        if err is not None:
            print(f"ERROR: baseline wallet-balances call failed: {err.text}")
            sys.exit(1)
        check("baseline call -> 200", True)

    # --- Insert this run's test data on the reused Owner/Member family ---
    async with async_session_factory() as session:
        wallet_uzs_active = Wallet(family_budget_id=family_budget_id, name=f"WB-UZS-{suffix}", currency="UZS")
        wallet_usd_active = Wallet(family_budget_id=family_budget_id, name=f"WB-USD-{suffix}", currency="USD")
        wallet_uzs_deleted = Wallet(
            family_budget_id=family_budget_id,
            name=f"WB-UZS-Deleted-{suffix}",
            currency="UZS",
            is_deleted=True,
            deleted_at=datetime.now(UTC),
        )
        income_cat = IncomeCategory(family_budget_id=family_budget_id, name=f"WB-Income-{suffix}")
        expense_top = ExpenseCategory(family_budget_id=family_budget_id, name=f"WB-Top-{suffix}")
        session.add_all([wallet_uzs_active, wallet_usd_active, wallet_uzs_deleted, income_cat, expense_top])
        await session.flush()

        expense_sub = ExpenseCategory(
            family_budget_id=family_budget_id, name=f"WB-Sub-{suffix}", parent_id=expense_top.id
        )
        session.add(expense_sub)
        await session.flush()

        d = datetime(2026, 5, 5, 10, 0, tzinfo=UTC)

        txns = [
            # (a) income on active UZS wallet
            Transaction(
                family_budget_id=family_budget_id, type="income", wallet_id=wallet_uzs_active.id, amount=1000,
                income_category_id=income_cat.id, created_by_user_id=owner.id, transaction_date=d,
            ),
            # (b) expense on active UZS wallet
            Transaction(
                family_budget_id=family_budget_id, type="expense", wallet_id=wallet_uzs_active.id, amount=300,
                expense_category_id=expense_sub.id, created_by_user_id=owner.id, transaction_date=d,
            ),
            # (c) income on SOFT-DELETED UZS wallet -- must still count
            Transaction(
                family_budget_id=family_budget_id, type="income", wallet_id=wallet_uzs_deleted.id, amount=700,
                income_category_id=income_cat.id, created_by_user_id=owner.id, transaction_date=d,
            ),
            # (d) expense on SOFT-DELETED UZS wallet -- must still count
            Transaction(
                family_budget_id=family_budget_id, type="expense", wallet_id=wallet_uzs_deleted.id, amount=100,
                expense_category_id=expense_sub.id, created_by_user_id=owner.id, transaction_date=d,
            ),
            # (e) income on active USD wallet
            Transaction(
                family_budget_id=family_budget_id, type="income", wallet_id=wallet_usd_active.id, amount=50,
                income_category_id=income_cat.id, created_by_user_id=owner.id, transaction_date=d,
            ),
            # (f) expense on active USD wallet
            Transaction(
                family_budget_id=family_budget_id, type="expense", wallet_id=wallet_usd_active.id, amount=20,
                expense_category_id=expense_sub.id, created_by_user_id=owner.id, transaction_date=d,
            ),
            # (g) same-currency transfer: active UZS -> soft-deleted UZS wallet (nets to 0 at currency level)
            Transaction(
                family_budget_id=family_budget_id, type="transfer", wallet_id=wallet_uzs_active.id,
                to_wallet_id=wallet_uzs_deleted.id, amount=200, to_amount=200,
                created_by_user_id=owner.id, transaction_date=d,
            ),
            # (h) cross-currency transfer: active UZS -> active USD
            Transaction(
                family_budget_id=family_budget_id, type="transfer", wallet_id=wallet_uzs_active.id,
                to_wallet_id=wallet_usd_active.id, amount=100_000, to_amount=8,
                created_by_user_id=owner.id, transaction_date=d,
            ),
            # (i) SOFT-DELETED transaction -- must be excluded entirely
            Transaction(
                family_budget_id=family_budget_id, type="income", wallet_id=wallet_uzs_active.id, amount=99_999,
                income_category_id=income_cat.id, created_by_user_id=owner.id, transaction_date=d,
                is_deleted=True,
            ),
        ]
        session.add_all(txns)
        await session.commit()

    # Expected deltas (see task file "Balance formula"):
    # UZS: income 1000+700=1700, expense 300+100=400,
    #      transfer_net = (-200+200) [same-currency, g] + (-100000) [h, from-side] = -100000
    #      balance delta = 1700 - 400 - 100000 = -98700
    # USD: income 50, expense 20, transfer_net = +8 [h, to-side]
    #      balance delta = 50 - 20 + 8 = 38
    # The (i) soft-deleted transaction (+99999) is deliberately NOT in this
    # math -- if the endpoint failed to exclude it, the UZS check below
    # would fail by exactly 99999.
    expected_uzs_delta = -98_700
    expected_usd_delta = 38

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        print("\n=== Wallet balances: fixed order, schema ===")
        after, err = await get_balances(client, owner_headers)
        check("after-insert call -> 200", err is None, err.text if err else "")
        raw = after["raw"] if after else {}
        balances_list = raw.get("balances", [])
        check(
            "response has exactly 2 entries, order UZS then USD",
            [b["currency"] for b in balances_list] == ["UZS", "USD"],
            str(balances_list),
        )
        check(
            "each entry has exactly {currency, balance} keys",
            all(set(b.keys()) == {"currency", "balance"} for b in balances_list),
            str(balances_list),
        )

        print("\n=== Wallet balances: delta vs baseline (all-time, incl. soft-deleted wallet, excl. soft-deleted txn) ===")
        after_by_currency = after["by_currency"] if after else {}
        base_by_currency = baseline["by_currency"]

        uzs_delta = after_by_currency.get("UZS", 0) - base_by_currency.get("UZS", 0)
        usd_delta = after_by_currency.get("USD", 0) - base_by_currency.get("USD", 0)

        check(
            f"UZS balance delta == {expected_uzs_delta} "
            "(proves soft-deleted-wallet txns included AND soft-deleted txn excluded)",
            uzs_delta == expected_uzs_delta,
            f"before={base_by_currency.get('UZS')} after={after_by_currency.get('UZS')} delta={uzs_delta}",
        )
        check(
            f"USD balance delta == {expected_usd_delta}",
            usd_delta == expected_usd_delta,
            f"before={base_by_currency.get('USD')} after={after_by_currency.get('USD')} delta={usd_delta}",
        )

        print("\n=== Member read access (no 403, same family-wide totals as Owner) ===")
        member_after, err = await get_balances(client, member_headers)
        check("Member GET wallet-balances -> 200", err is None, err.text if err else "")
        check(
            "Member sees identical balances to Owner (family-wide, not per-user)",
            member_after is not None and member_after["by_currency"] == after_by_currency,
            f"owner={after_by_currency} member={member_after['by_currency'] if member_after else None}",
        )

    # --- Isolated brand-new family with zero wallets, for the absolute-zero check ---
    print("\n=== Zero wallets of a currency -> balance: 0 (isolated fresh family) ===")
    async with async_session_factory() as session:
        fresh_family = FamilyBudget()
        session.add(fresh_family)
        await session.flush()

        fresh_telegram_id = random.randint(900_000_000, 999_999_999)
        while await session.scalar(select(User).where(User.telegram_id == fresh_telegram_id)) is not None:
            fresh_telegram_id = random.randint(900_000_000, 999_999_999)

        fresh_user = User(
            telegram_id=fresh_telegram_id,
            family_budget_id=fresh_family.id,
            role="owner",
            first_name="FreshFamily",
            username=None,
            language="ru",
            is_deleted=False,
        )
        session.add(fresh_user)
        await session.commit()

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        fresh_headers = auth_header(fresh_telegram_id, "FreshFamily")
        fresh_result, err = await get_balances(client, fresh_headers)
        check("fresh-family GET wallet-balances -> 200", err is None, err.text if err else "")
        fresh_by_currency = fresh_result["by_currency"] if fresh_result else {}
        check(
            "fresh family (zero wallets) -> UZS balance 0",
            fresh_by_currency.get("UZS") == 0,
            str(fresh_by_currency),
        )
        check(
            "fresh family (zero wallets) -> USD balance 0",
            fresh_by_currency.get("USD") == 0,
            str(fresh_by_currency),
        )

    print(f"\n===== SUMMARY: {passed} passed, {failed} failed =====")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())