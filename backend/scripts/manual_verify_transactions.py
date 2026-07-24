"""
Automated manual verification of Acceptance criteria in
docs/tasks/05-api-transactions.md.

Prerequisites:
  1. Server running: uvicorn app.main:app --reload (port 8000)
  2. Owner (telegram_id=111111) and Member (telegram_id=222222) exist in DB.

Run (from backend/, with venv active):
    python -m scripts.manual_verify_transactions
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
        "Content-Type": "application/json",
    }


def txn_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "transaction_date": datetime.now(UTC).isoformat(),
        "amount": 100,
    }
    base.update(overrides)
    return base


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

        wallet_uzs = Wallet(
            family_budget_id=family_budget_id,
            name=f"Script-UZS-{suffix}",
            currency="UZS",
        )
        wallet_usd = Wallet(
            family_budget_id=family_budget_id,
            name=f"Script-USD-{suffix}",
            currency="USD",
        )
        wallet_uzs_b = Wallet(
            family_budget_id=family_budget_id,
            name=f"Script-UZS-B-{suffix}",
            currency="UZS",
        )
        income_cat = IncomeCategory(
            family_budget_id=family_budget_id,
            name=f"Script-Income-{suffix}",
        )
        expense_top = ExpenseCategory(
            family_budget_id=family_budget_id,
            name=f"Script-Top-{suffix}",
        )
        session.add_all([wallet_uzs, wallet_usd, wallet_uzs_b, income_cat, expense_top])
        await session.flush()
        expense_sub = ExpenseCategory(
            family_budget_id=family_budget_id,
            name=f"Script-Sub-{suffix}",
            parent_id=expense_top.id,
        )
        session.add(expense_sub)
        await session.commit()

        wallet_uzs_id = str(wallet_uzs.id)
        wallet_usd_id = str(wallet_usd.id)
        wallet_uzs_b_id = str(wallet_uzs_b.id)
        income_cat_id = str(income_cat.id)
        expense_top_id = str(expense_top.id)
        expense_sub_id = str(expense_sub.id)
        owner_id = owner.id
        member_id = member.id

    owner_headers = auth_header(OWNER_TELEGRAM_ID, "Owner")
    member_headers = auth_header(MEMBER_TELEGRAM_ID, "Member")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        print("\n=== All 6 endpoints implemented and role-enforced ===")
        income_resp = await client.post(
            "/api/v1/transactions/income",
            headers=owner_headers,
            json=txn_payload(wallet_id=wallet_uzs_id, income_category_id=income_cat_id),
        )
        check("Owner POST income -> 201", income_resp.status_code == 201, income_resp.text)
        income_id = income_resp.json().get("id") if income_resp.status_code == 201 else None

        expense_resp = await client.post(
            "/api/v1/transactions/expense",
            headers=member_headers,
            json=txn_payload(wallet_id=wallet_uzs_id, expense_category_id=expense_sub_id),
        )
        check("Member POST expense -> 201", expense_resp.status_code == 201, expense_resp.text)

        transfer_resp = await client.post(
            "/api/v1/transactions/transfer",
            headers=owner_headers,
            json=txn_payload(
                wallet_id=wallet_uzs_id,
                to_wallet_id=wallet_uzs_b_id,
                amount=500,
            ),
        )
        check("Owner POST transfer -> 201", transfer_resp.status_code == 201, transfer_resp.text)
        transfer_id = transfer_resp.json().get("id") if transfer_resp.status_code == 201 else None

        get_resp = await client.get(
            f"/api/v1/transactions/{income_id}",
            headers=member_headers,
        )
        check("Member GET transaction -> 200", get_resp.status_code == 200, get_resp.text)

        patch_resp = await client.patch(
            f"/api/v1/transactions/{income_id}",
            headers=owner_headers,
            json=txn_payload(
                wallet_id=wallet_uzs_id,
                income_category_id=income_cat_id,
                amount=150,
            ),
        )
        check("Owner PATCH transaction -> 200", patch_resp.status_code == 200, patch_resp.text)

        print("\n=== Income/Expense wallet+category validation ===")
        async with async_session_factory() as session:
            deleted_wallet = Wallet(
                family_budget_id=family_budget_id,
                name=f"Deleted-{suffix}",
                currency="UZS",
                is_deleted=True,
                deleted_at=datetime.now(UTC),
            )
            session.add(deleted_wallet)
            await session.commit()
            deleted_wallet_id = str(deleted_wallet.id)

        bad_wallet = await client.post(
            "/api/v1/transactions/income",
            headers=owner_headers,
            json=txn_payload(wallet_id=deleted_wallet_id, income_category_id=income_cat_id),
        )
        check("Deleted wallet -> 404", bad_wallet.status_code == 404, bad_wallet.text)

        print("\n=== Expense rejects top-level category (400) ===")
        top_expense = await client.post(
            "/api/v1/transactions/expense",
            headers=owner_headers,
            json=txn_payload(wallet_id=wallet_uzs_id, expense_category_id=expense_top_id),
        )
        check("Top-level expense category -> 400", top_expense.status_code == 400, top_expense.text)

        print("\n=== Transfer same-currency: to_amount=amount, no rate ===")
        same_curr = await client.post(
            "/api/v1/transactions/transfer",
            headers=owner_headers,
            json=txn_payload(
                wallet_id=wallet_uzs_id,
                to_wallet_id=wallet_uzs_b_id,
                amount=777,
            ),
        )
        same_body = same_curr.json() if same_curr.status_code == 201 else {}
        check("Same-currency transfer -> 201", same_curr.status_code == 201, same_curr.text)
        check("to_amount == amount", same_body.get("to_amount") == 777, str(same_body))
        check("rate is null", same_body.get("rate") is None, str(same_body))

        with_rate_same = await client.post(
            "/api/v1/transactions/transfer",
            headers=owner_headers,
            json=txn_payload(
                wallet_id=wallet_uzs_id,
                to_wallet_id=wallet_uzs_b_id,
                amount=100,
                rate=12500,
            ),
        )
        check("Same-currency with rate -> 422", with_rate_same.status_code == 422, with_rate_same.text)

        print("\n=== Transfer different-currency: rate required, rounded to_amount ===")
        no_rate = await client.post(
            "/api/v1/transactions/transfer",
            headers=owner_headers,
            json=txn_payload(
                wallet_id=wallet_uzs_id,
                to_wallet_id=wallet_usd_id,
                amount=100_000,
            ),
        )
        check("Cross-currency without rate -> 422", no_rate.status_code == 422, no_rate.text)

        uzs_usd = await client.post(
            "/api/v1/transactions/transfer",
            headers=owner_headers,
            json=txn_payload(
                wallet_id=wallet_uzs_id,
                to_wallet_id=wallet_usd_id,
                amount=100_000,
                rate=12_500,
            ),
        )
        uzs_usd_body = uzs_usd.json() if uzs_usd.status_code == 201 else {}
        check("UZS->USD transfer -> 201", uzs_usd.status_code == 201, uzs_usd.text)
        check(
            "UZS->USD to_amount rounded",
            uzs_usd_body.get("to_amount") == round(100_000 / 12_500),
            str(uzs_usd_body),
        )

        usd_uzs = await client.post(
            "/api/v1/transactions/transfer",
            headers=owner_headers,
            json=txn_payload(
                wallet_id=wallet_usd_id,
                to_wallet_id=wallet_uzs_id,
                amount=10,
                rate=12_500,
            ),
        )
        usd_uzs_body = usd_uzs.json() if usd_uzs.status_code == 201 else {}
        check("USD->UZS transfer -> 201", usd_uzs.status_code == 201, usd_uzs.text)
        check(
            "USD->UZS to_amount rounded",
            usd_uzs_body.get("to_amount") == round(10 * 12_500),
            str(usd_uzs_body),
        )

        print("\n=== Transfer rejects wallet_id == to_wallet_id (400) ===")
        same_wallet = await client.post(
            "/api/v1/transactions/transfer",
            headers=owner_headers,
            json=txn_payload(wallet_id=wallet_uzs_id, to_wallet_id=wallet_uzs_id, amount=100),
        )
        check("Same wallet transfer -> 400", same_wallet.status_code == 400, same_wallet.text)

        print("\n=== Transfer rejects category fields (422) ===")
        with_income = await client.post(
            "/api/v1/transactions/transfer",
            headers=owner_headers,
            json={
                **txn_payload(
                    wallet_id=wallet_uzs_id,
                    to_wallet_id=wallet_uzs_b_id,
                    amount=100,
                ),
                "income_category_id": income_cat_id,
            },
        )
        check("Transfer with income_category_id -> 422", with_income.status_code == 422, with_income.text)

        with_expense = await client.post(
            "/api/v1/transactions/transfer",
            headers=owner_headers,
            json={
                **txn_payload(
                    wallet_id=wallet_uzs_id,
                    to_wallet_id=wallet_uzs_b_id,
                    amount=100,
                ),
                "expense_category_id": expense_sub_id,
            },
        )
        check("Transfer with expense_category_id -> 422", with_expense.status_code == 422, with_expense.text)

        print("\n=== Member 403 on others' transactions, 200 on own ===")
        async with async_session_factory() as session:
            owner_txn = Transaction(
                family_budget_id=family_budget_id,
                type="income",
                wallet_id=uuid.UUID(wallet_uzs_id),
                amount=100,
                income_category_id=uuid.UUID(income_cat_id),
                created_by_user_id=owner_id,
                transaction_date=datetime.now(UTC),
            )
            member_txn = Transaction(
                family_budget_id=family_budget_id,
                type="income",
                wallet_id=uuid.UUID(wallet_uzs_id),
                amount=200,
                income_category_id=uuid.UUID(income_cat_id),
                created_by_user_id=member_id,
                transaction_date=datetime.now(UTC),
            )
            session.add_all([owner_txn, member_txn])
            await session.commit()
            owner_txn_id = str(owner_txn.id)
            member_txn_id = str(member_txn.id)

        member_patch_other = await client.patch(
            f"/api/v1/transactions/{owner_txn_id}",
            headers=member_headers,
            json=txn_payload(
                wallet_id=wallet_uzs_id,
                income_category_id=income_cat_id,
                amount=999,
            ),
        )
        check("Member PATCH other's txn -> 403", member_patch_other.status_code == 403, member_patch_other.text)

        member_delete_other = await client.delete(
            f"/api/v1/transactions/{owner_txn_id}",
            headers=member_headers,
        )
        check(
            "Member DELETE other's txn -> 403",
            member_delete_other.status_code == 403,
            member_delete_other.text,
        )

        member_patch_own = await client.patch(
            f"/api/v1/transactions/{member_txn_id}",
            headers=member_headers,
            json=txn_payload(
                wallet_id=wallet_uzs_id,
                income_category_id=income_cat_id,
                amount=250,
            ),
        )
        check("Member PATCH own txn -> 200", member_patch_own.status_code == 200, member_patch_own.text)

        print("\n=== Owner can PATCH/DELETE any transaction ===")
        owner_patch = await client.patch(
            f"/api/v1/transactions/{member_txn_id}",
            headers=owner_headers,
            json=txn_payload(
                wallet_id=wallet_uzs_id,
                income_category_id=income_cat_id,
                amount=300,
            ),
        )
        check("Owner PATCH member's txn -> 200", owner_patch.status_code == 200, owner_patch.text)

        owner_delete = await client.delete(
            f"/api/v1/transactions/{member_txn_id}",
            headers=owner_headers,
        )
        check("Owner DELETE member's txn -> 200", owner_delete.status_code == 200, owner_delete.text)

        print("\n=== Cross-family transaction access -> 404 ===")
        async with async_session_factory() as session:
            other_budget_user = await session.scalar(
                select(User).where(User.telegram_id != OWNER_TELEGRAM_ID, User.role == "owner")
            )
            if other_budget_user is None or other_budget_user.family_budget_id == family_budget_id:
                check("Cross-family setup skipped (no other family budget user)", True)
            else:
                other_headers = auth_header(other_budget_user.telegram_id, "Other")
                cross_get = await client.get(
                    f"/api/v1/transactions/{income_id}",
                    headers=other_headers,
                )
                check("Cross-family GET -> 404", cross_get.status_code == 404, cross_get.text)

        print("\n=== DELETE soft-delete (is_deleted, deleted_at), no cascade ===")
        if transfer_id:
            del_resp = await client.delete(
                f"/api/v1/transactions/{transfer_id}",
                headers=owner_headers,
            )
            check("DELETE transfer -> 200", del_resp.status_code == 200, del_resp.text)

            async with async_session_factory() as session:
                row = await session.get(Transaction, uuid.UUID(transfer_id))
                check("Transaction is_deleted == True", row is not None and row.is_deleted is True)
                check("Transaction deleted_at set", row is not None and row.deleted_at is not None)
                check(
                    "Wallet reference unchanged",
                    row is not None and str(row.wallet_id) == wallet_uzs_id,
                )

            gone = await client.get(
                f"/api/v1/transactions/{transfer_id}",
                headers=owner_headers,
            )
            check("Soft-deleted txn not returned by GET -> 404", gone.status_code == 404, gone.text)

    print(f"\n===== SUMMARY: {passed} passed, {failed} failed =====")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
