"""QA m3-2: onboarding edge cases not covered by test_m3_onboarding.py (found by mutation)."""
import pytest
from sqlalchemy import update

from app.models.transaction import Transaction
from app.models.user import User
from tests.test_m3_onboarding import POST_URL, URL, _add_expense, _tid
from tests.test_members import api_client, auth_headers, create_user_with_budget  # noqa: F401

pytestmark = pytest.mark.anyio


async def test_deleted_operation_is_not_a_first_operation(api_client) -> None:
    client, session = api_client
    tid = _tid()
    owner, budget = await create_user_with_budget(session, telegram_id=tid)
    await _add_expense(session, owner, budget)
    await session.execute(
        update(Transaction).where(Transaction.family_budget_id == budget.id).values(is_deleted=True)
    )
    await session.flush()
    r = await client.get(URL, headers=auth_headers(tid))
    assert r.json()["steps"]["first_operation"] is False


async def test_operation_of_another_family_does_not_count(api_client) -> None:
    client, session = api_client
    tid, other = _tid(), _tid()
    await create_user_with_budget(session, telegram_id=tid)
    o_owner, o_budget = await create_user_with_budget(session, telegram_id=other)
    await _add_expense(session, o_owner, o_budget)
    r = await client.get(URL, headers=auth_headers(tid))
    assert r.json()["steps"]["first_operation"] is False
    assert r.json()["show"] is True


async def test_removed_member_does_not_count_as_invited(api_client) -> None:
    client, session = api_client
    tid = _tid()
    _, budget = await create_user_with_budget(session, telegram_id=tid)
    member, _ = await create_user_with_budget(
        session, telegram_id=tid + 1, role="member", family_budget_id=budget.id
    )
    await session.execute(update(User).where(User.id == member.id).values(is_deleted=True))
    await session.flush()
    r = await client.get(URL, headers=auth_headers(tid))
    assert r.json()["steps"]["family_invited"] is False


async def test_default_wallet_flag_is_persisted_not_only_in_memory(api_client) -> None:
    client, session = api_client
    tid = _tid()
    await create_user_with_budget(session, telegram_id=tid)
    await session.commit()
    assert (await client.post(POST_URL, headers=auth_headers(tid))).status_code == 200
    await session.rollback()  # drop anything the endpoint did not commit
    session.expire_all()
    r = await client.get(URL, headers=auth_headers(tid))
    assert r.json()["steps"]["default_wallet_checked"] is True


async def test_member_post_sets_only_own_flag_and_owner_card_unchanged(api_client) -> None:
    client, session = api_client
    tid = _tid()
    _, budget = await create_user_with_budget(session, telegram_id=tid)
    await create_user_with_budget(session, telegram_id=tid + 1, role="member", family_budget_id=budget.id)
    r = await client.post(POST_URL, headers=auth_headers(tid + 1))
    assert r.status_code == 200 and r.json()["show"] is False
    assert r.json()["steps"]["default_wallet_checked"] is True
    owner = (await client.get(URL, headers=auth_headers(tid))).json()
    assert owner["steps"]["default_wallet_checked"] is False and owner["show"] is True
