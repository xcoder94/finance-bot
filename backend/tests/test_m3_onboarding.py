import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from app.models.transaction import Transaction
from app.models.wallet import Wallet
from tests.test_members import api_client, auth_headers, create_user_with_budget  # noqa: F401

pytestmark = pytest.mark.anyio

URL = "/api/v1/me/onboarding"
POST_URL = "/api/v1/me/onboarding/default-wallet-checked"


def _tid() -> int:
    return int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000


async def _add_expense(session: AsyncSession, user, budget, *, is_demo: bool = False) -> None:
    wallet = Wallet(family_budget_id=budget.id, name="W", currency="UZS")
    cat = ExpenseCategory(family_budget_id=budget.id, name="Еда")
    session.add_all([wallet, cat])
    await session.flush()
    session.add(
        Transaction(
            family_budget_id=budget.id,
            type="expense",
            wallet_id=wallet.id,
            amount=1000,
            expense_category_id=cat.id,
            created_by_user_id=user.id,
            transaction_date=datetime.now(UTC),
            is_demo=is_demo,
        )
    )
    await session.flush()


async def test_new_family_shows_all_steps_false(api_client) -> None:
    client, session = api_client
    tid = _tid()
    await create_user_with_budget(session, telegram_id=tid)
    r = await client.get(URL, headers=auth_headers(tid))
    assert r.status_code == 200
    assert r.json() == {
        "show": True,
        "steps": {"first_operation": False, "default_wallet_checked": False, "family_invited": False},
    }


async def test_first_operation_step_by_any_member_and_demo_ignored(api_client) -> None:
    client, session = api_client
    tid = _tid()
    owner, budget = await create_user_with_budget(session, telegram_id=tid)
    member, _ = await create_user_with_budget(
        session, telegram_id=tid + 1, role="member", family_budget_id=budget.id
    )
    await _add_expense(session, owner, budget, is_demo=True)
    r = await client.get(URL, headers=auth_headers(tid))
    assert r.json()["steps"]["first_operation"] is False
    await _add_expense(session, member, budget)
    r = await client.get(URL, headers=auth_headers(tid))
    assert r.json()["steps"]["first_operation"] is True


async def test_default_wallet_post_sets_step_and_is_idempotent(api_client) -> None:
    client, session = api_client
    tid = _tid()
    await create_user_with_budget(session, telegram_id=tid)
    r1 = await client.post(POST_URL, headers=auth_headers(tid))
    r2 = await client.post(POST_URL, headers=auth_headers(tid))
    assert r1.status_code == 200 and r2.status_code == 200
    assert r2.json()["steps"]["default_wallet_checked"] is True
    r = await client.get(URL, headers=auth_headers(tid))
    assert r.json()["steps"]["default_wallet_checked"] is True


async def test_flag_is_per_user(api_client) -> None:
    client, session = api_client
    tid = _tid()
    _, budget = await create_user_with_budget(session, telegram_id=tid)
    await create_user_with_budget(session, telegram_id=tid + 1, role="member", family_budget_id=budget.id)
    await client.post(POST_URL, headers=auth_headers(tid + 1))
    r = await client.get(URL, headers=auth_headers(tid))
    assert r.json()["steps"]["default_wallet_checked"] is False


async def test_second_member_marks_family_invited(api_client) -> None:
    client, session = api_client
    tid = _tid()
    _, budget = await create_user_with_budget(session, telegram_id=tid)
    await create_user_with_budget(session, telegram_id=tid + 1, role="member", family_budget_id=budget.id)
    r = await client.get(URL, headers=auth_headers(tid))
    assert r.json()["steps"]["family_invited"] is True


async def test_invite_link_open_and_regenerate_mark_step_but_existing_token_alone_does_not(
    api_client,
) -> None:
    client, session = api_client
    tid = _tid()
    await create_user_with_budget(session, telegram_id=tid)
    assert (await client.get(URL, headers=auth_headers(tid))).json()["steps"]["family_invited"] is False
    assert (await client.get("/api/v1/members/invite-link", headers=auth_headers(tid))).status_code == 200
    assert (await client.get(URL, headers=auth_headers(tid))).json()["steps"]["family_invited"] is True

    tid2 = _tid()
    await create_user_with_budget(session, telegram_id=tid2)
    assert (await client.post("/api/v1/members/invite-link/regenerate", headers=auth_headers(tid2))).status_code == 200
    assert (await client.get(URL, headers=auth_headers(tid2))).json()["steps"]["family_invited"] is True


async def test_all_done_hides_for_owner(api_client) -> None:
    client, session = api_client
    tid = _tid()
    owner, budget = await create_user_with_budget(session, telegram_id=tid)
    await create_user_with_budget(session, telegram_id=tid + 1, role="member", family_budget_id=budget.id)
    await _add_expense(session, owner, budget)
    await client.post(POST_URL, headers=auth_headers(tid))
    r = await client.get(URL, headers=auth_headers(tid))
    assert r.json()["show"] is False
    assert all(r.json()["steps"].values())


async def test_member_never_sees_onboarding(api_client) -> None:
    client, session = api_client
    tid = _tid()
    _, budget = await create_user_with_budget(session, telegram_id=tid)
    await create_user_with_budget(session, telegram_id=tid + 1, role="member", family_budget_id=budget.id)
    r = await client.get(URL, headers=auth_headers(tid + 1))
    assert r.status_code == 200
    assert r.json()["show"] is False


async def test_requires_auth(api_client) -> None:
    client, _ = api_client
    assert (await client.get(URL)).status_code in (401, 403)
    assert (await client.post(POST_URL)).status_code in (401, 403)
    assert (await client.get(URL, headers=auth_headers(_tid()))).status_code == 401
    assert (await client.post(POST_URL, headers=auth_headers(_tid()))).status_code == 401
