"""
Automated manual verification of the GET /api/v1/me fix described in
the "Fix: GET /api/v1/me returns app-level user data (2026-07-18)"
section of docs/tasks/01-auth-telegram.md.

Prerequisites:
  1. Server running: uvicorn app.main:app --reload (port 8000)
  2. Owner (telegram_id=111111) and Member (telegram_id=222222) exist in DB.

Run (from backend/, with venv active):
    python -m scripts.manual_verify_me_endpoint

Design note: reuses the existing Owner/Member test users for the 200 case
(never inserts/deletes them, per project convention). For the 404 and 403
cases it creates its own throwaway data with a unique telegram_id per run,
so repeated runs don't collide and nothing needs cleanup.
"""

import asyncio
import random
import sys

import httpx
from sqlalchemy import select

from app.db import async_session_factory
from app.models.user import User
from scripts.gen_test_initdata import build_init_data

BASE_URL = "http://127.0.0.1:8000"
OWNER_TELEGRAM_ID = 111111
MEMBER_TELEGRAM_ID = 222222

EXPECTED_FIELDS = {
    "id",
    "telegram_id",
    "family_budget_id",
    "role",
    "first_name",
    "username",
    "language",
}

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

        # Unique telegram_id for the 404 case (guaranteed not in DB).
        unknown_telegram_id = random.randint(900_000_000, 999_999_999)
        while await session.scalar(select(User).where(User.telegram_id == unknown_telegram_id)) is not None:
            unknown_telegram_id = random.randint(900_000_000, 999_999_999)

        # Throwaway soft-deleted user for the 403 case.
        removed_telegram_id = random.randint(900_000_000, 999_999_999)
        while await session.scalar(select(User).where(User.telegram_id == removed_telegram_id)) is not None:
            removed_telegram_id = random.randint(900_000_000, 999_999_999)

        removed_user = User(
            telegram_id=removed_telegram_id,
            family_budget_id=family_budget_id,
            role="member",
            first_name="Removed",
            username=None,
            language="ru",
            is_deleted=True,
        )
        session.add(removed_user)
        await session.commit()

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        print("\n=== 404: telegram_id with no User row (not onboarded) ===")
        resp_404 = await client.get(
            "/api/v1/me", headers=auth_header(unknown_telegram_id, "Ghost")
        )
        check("status 404", resp_404.status_code == 404, resp_404.text)
        check(
            'detail == "not_onboarded"',
            resp_404.status_code == 404 and resp_404.json().get("detail") == "not_onboarded",
            resp_404.text,
        )

        print("\n=== 403: telegram_id matching a soft-deleted User (removed member) ===")
        resp_403 = await client.get(
            "/api/v1/me", headers=auth_header(removed_telegram_id, "Removed")
        )
        check("status 403", resp_403.status_code == 403, resp_403.text)
        check(
            'detail == "removed_from_family"',
            resp_403.status_code == 403 and resp_403.json().get("detail") == "removed_from_family",
            resp_403.text,
        )

        print("\n=== 200: active Owner ===")
        resp_owner = await client.get("/api/v1/me", headers=auth_header(OWNER_TELEGRAM_ID, "Owner"))
        check("status 200", resp_owner.status_code == 200, resp_owner.text)
        body = resp_owner.json() if resp_owner.status_code == 200 else {}
        check("response has exactly the 7 expected fields", set(body.keys()) == EXPECTED_FIELDS, str(body.keys()))
        check("id matches DB", body.get("id") == str(owner.id), str(body.get("id")))
        check("telegram_id matches DB", body.get("telegram_id") == owner.telegram_id, str(body.get("telegram_id")))
        check(
            "family_budget_id matches DB",
            body.get("family_budget_id") == str(owner.family_budget_id),
            str(body.get("family_budget_id")),
        )
        check("role matches DB", body.get("role") == owner.role, str(body.get("role")))
        check("first_name matches DB", body.get("first_name") == owner.first_name, str(body.get("first_name")))
        check("username matches DB", body.get("username") == owner.username, str(body.get("username")))
        check("language matches DB", body.get("language") == owner.language, str(body.get("language")))

        print("\n=== 200: active Member (spot-check role differs from Owner) ===")
        resp_member = await client.get("/api/v1/me", headers=auth_header(MEMBER_TELEGRAM_ID, "Member"))
        check("status 200", resp_member.status_code == 200, resp_member.text)
        member_body = resp_member.json() if resp_member.status_code == 200 else {}
        check("Member role matches DB", member_body.get("role") == member.role, str(member_body.get("role")))
        check(
            "Member family_budget_id matches Owner's (same family)",
            member_body.get("family_budget_id") == str(family_budget_id),
            str(member_body.get("family_budget_id")),
        )

        print("\n=== 401 regression: unchanged behavior for bad auth ===")
        resp_401 = await client.get("/api/v1/me", headers={"Authorization": "tma garbage"})
        check("bad initData -> 401", resp_401.status_code == 401, resp_401.text)
        resp_401_missing = await client.get("/api/v1/me")
        check("missing Authorization -> 401", resp_401_missing.status_code == 401, resp_401_missing.text)

    print(f"\n===== SUMMARY: {passed} passed, {failed} failed =====")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
