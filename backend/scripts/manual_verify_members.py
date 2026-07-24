"""
Automated manual verification of Acceptance criteria in
docs/tasks/13-api-family-members.md.

Prerequisites:
  1. Server running: uvicorn app.main:app --reload (port 8000)

Design note: unlike most other manual_verify_*.py scripts, this one does
NOT reuse the shared Owner (111111) / Member (222222) test family, because
two of the operations under test are destructive and irreversible on
whatever family they run against:
  - POST /members/invite-link/regenerate permanently replaces
    family_budgets.invite_token
  - DELETE /members/{id} permanently soft-deletes a member

Running either against the shared 111111/222222 family would corrupt
fixtures other scripts (and the user) rely on. So this script creates one
brand-new, throwaway FamilyBudget + Owner + Member, used only here, and
never touched again after this run.

Run (from backend/, with venv active):
    python -m scripts.manual_verify_members
"""

import asyncio
import random
import sys
from datetime import UTC, datetime

import httpx
from sqlalchemy import select

from app.db import async_session_factory
from app.models.family_budget import FamilyBudget
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from bot.onboarding import get_family_budget_by_invite_token
from scripts.gen_test_initdata import build_init_data

BASE_URL = "http://127.0.0.1:8000"

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


async def random_unused_telegram_id(session) -> int:
    telegram_id = random.randint(900_000_000, 999_999_999)
    while await session.scalar(select(User).where(User.telegram_id == telegram_id)) is not None:
        telegram_id = random.randint(900_000_000, 999_999_999)
    return telegram_id


async def main() -> None:
    print("Setting up isolated throwaway family (Owner + Member)...")
    async with async_session_factory() as session:
        family = FamilyBudget(invite_token="verify-members-initial-token")
        session.add(family)
        await session.flush()

        owner_tid = await random_unused_telegram_id(session)
        owner = User(
            telegram_id=owner_tid,
            family_budget_id=family.id,
            role="owner",
            first_name="VerifyOwner",
            username=None,
            language="ru",
        )
        session.add(owner)

        member_tid = await random_unused_telegram_id(session)
        member = User(
            telegram_id=member_tid,
            family_budget_id=family.id,
            role="member",
            first_name="VerifyMember",
            username="verify_member",
            language="ru",
        )
        session.add(member)
        await session.flush()

        wallet = Wallet(family_budget_id=family.id, name="VerifyWallet", currency="UZS")
        income_cat = IncomeCategory(family_budget_id=family.id, name="VerifyIncome")
        session.add_all([wallet, income_cat])
        await session.flush()

        # A transaction created by the Member, to later confirm it survives
        # the Member's removal untouched (PRD §8 — no cascade).
        member_txn = Transaction(
            family_budget_id=family.id,
            type="income",
            wallet_id=wallet.id,
            amount=123,
            income_category_id=income_cat.id,
            created_by_user_id=member.id,
            transaction_date=datetime.now(UTC),
        )
        session.add(member_txn)
        await session.commit()

        family_id = family.id
        owner_id = owner.id
        member_id = member.id
        member_txn_id = member_txn.id
        original_token = family.invite_token

    owner_headers = auth_header(owner_tid, "VerifyOwner")
    member_headers = auth_header(member_tid, "VerifyMember")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        print("\n=== GET /members ===")
        resp = await client.get("/api/v1/members", headers=owner_headers)
        check("Owner GET /members -> 200", resp.status_code == 200, resp.text)
        by_id = {row["id"]: row for row in resp.json()} if resp.status_code == 200 else {}
        check(
            "list includes Owner row with role=owner",
            by_id.get(str(owner_id), {}).get("role") == "owner",
            str(by_id.get(str(owner_id))),
        )
        check(
            "list includes Member row with role=member, correct first_name/username",
            by_id.get(str(member_id), {}).get("role") == "member"
            and by_id.get(str(member_id), {}).get("first_name") == "VerifyMember"
            and by_id.get(str(member_id), {}).get("username") == "verify_member",
            str(by_id.get(str(member_id))),
        )

        resp = await client.get("/api/v1/members", headers=member_headers)
        check("Member GET /members -> 200 (read access, not Owner-only)", resp.status_code == 200, resp.text)

        print("\n=== GET /members/invite-link ===")
        resp = await client.get("/api/v1/members/invite-link", headers=owner_headers)
        check("Owner GET invite-link -> 200", resp.status_code == 200, resp.text)
        first_link = resp.json().get("invite_link", "") if resp.status_code == 200 else ""
        check(
            "invite-link contains the family's current invite_token",
            f"invite_{original_token}" in first_link,
            first_link,
        )

        resp = await client.get("/api/v1/members/invite-link", headers=member_headers)
        check("Member GET invite-link -> 403", resp.status_code == 403, resp.text)

        print("\n=== POST /members/invite-link/regenerate ===")
        resp = await client.post("/api/v1/members/invite-link/regenerate", headers=member_headers)
        check("Member POST regenerate -> 403", resp.status_code == 403, resp.text)

        resp = await client.post("/api/v1/members/invite-link/regenerate", headers=owner_headers)
        check("Owner POST regenerate -> 200", resp.status_code == 200, resp.text)
        new_link = resp.json().get("invite_link", "") if resp.status_code == 200 else ""
        check("new invite-link differs from the original", new_link != first_link, f"{new_link} == {first_link}")

        resp = await client.get("/api/v1/members/invite-link", headers=owner_headers)
        check(
            "subsequent GET invite-link now returns the regenerated link",
            resp.status_code == 200 and resp.json().get("invite_link") == new_link,
            resp.text,
        )

        print("\n=== Old token invalidated after regenerate ===")
        async with async_session_factory() as session:
            stale_lookup = await get_family_budget_by_invite_token(session, original_token)
        check(
            "bot's get_family_budget_by_invite_token(old_token) -> None "
            "(old /start invite_<token> link would now be rejected)",
            stale_lookup is None,
            f"got: {stale_lookup}",
        )

        print("\n=== DELETE /members/{id} — self-delete blocked ===")
        resp = await client.delete(f"/api/v1/members/{owner_id}", headers=owner_headers)
        check("Owner DELETE own id -> 400", resp.status_code == 400, resp.text)

        print("\n=== DELETE /members/{id} — role enforcement ===")
        resp = await client.delete(f"/api/v1/members/{member_id}", headers=member_headers)
        check("Member DELETE (any id) -> 403", resp.status_code == 403, resp.text)

        print("\n=== DELETE /members/{id} — cross-family 404 ===")
        resp = await client.get("/api/v1/me", headers=owner_headers)  # sanity, unrelated family not needed here
        random_uuid = "00000000-0000-0000-0000-000000000000"
        resp = await client.delete(f"/api/v1/members/{random_uuid}", headers=owner_headers)
        check("DELETE nonexistent/foreign id -> 404", resp.status_code == 404, resp.text)

        print("\n=== DELETE /members/{id} — actual removal ===")
        resp = await client.delete(f"/api/v1/members/{member_id}", headers=owner_headers)
        check("Owner DELETE Member -> 200", resp.status_code == 200, resp.text)
        body = resp.json() if resp.status_code == 200 else {}
        check(
            "response body has id/first_name/role of removed member",
            body.get("id") == str(member_id) and body.get("role") == "member",
            str(body),
        )

        resp = await client.get("/api/v1/members", headers=owner_headers)
        remaining_ids = {row["id"] for row in resp.json()} if resp.status_code == 200 else set()
        check("removed Member no longer appears in GET /members", str(member_id) not in remaining_ids, str(remaining_ids))

        resp = await client.delete(f"/api/v1/members/{member_id}", headers=owner_headers)
        check("repeat DELETE on same (already-removed) id -> 404", resp.status_code == 404, resp.text)

    print("\n=== DB-level check: removed Member's transaction is untouched ===")
    async with async_session_factory() as session:
        txn = await session.get(Transaction, member_txn_id)
        removed_user = await session.get(User, member_id)
        check(
            "transaction still references created_by_user_id == removed member's id",
            txn is not None and txn.created_by_user_id == member_id and not txn.is_deleted,
            f"txn={txn}",
        )
        check(
            "removed member row: is_deleted=True, deleted_at set, row still exists (soft-delete, not hard-delete)",
            removed_user is not None and removed_user.is_deleted is True and removed_user.deleted_at is not None,
            f"user={removed_user}",
        )

    print(f"\n===== SUMMARY: {passed} passed, {failed} failed =====")
    print(f"(isolated test family_budget_id={family_id}, never reused)")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
