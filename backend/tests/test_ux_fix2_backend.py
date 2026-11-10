import uuid
from datetime import UTC, datetime

import pytest

from app.models.expense_category import ExpenseCategory
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.wallet import Wallet
from tests.test_members import api_client, auth_headers, create_user_with_budget  # noqa: F401

pytestmark = pytest.mark.anyio

HIST = "/api/v1/transactions/history"
ONB = "/api/v1/me/onboarding"


def _tid() -> int:
    return int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000


def _params(**extra):
    return {"date_from": "2000-01-01T00:00:00Z", "date_to": "2100-01-01T00:00:00Z", **extra}


async def _seed(session, user, budget, n_uzs=3, n_usd=2):
    uzs = Wallet(family_budget_id=budget.id, name="U", currency="UZS")
    usd = Wallet(family_budget_id=budget.id, name="D", currency="USD")
    cat = ExpenseCategory(family_budget_id=budget.id, name="Food")
    session.add_all([uzs, usd, cat])
    await session.flush()
    for w, n in ((uzs, n_uzs), (usd, n_usd)):
        for _ in range(n):
            session.add(
                Transaction(
                    family_budget_id=budget.id, type="expense", wallet_id=w.id, amount=100,
                    expense_category_id=cat.id, created_by_user_id=user.id,
                    transaction_date=datetime.now(UTC),
                )
            )
    await session.flush()
    return uzs, usd


async def test_history_currency_filters_rows_and_total(api_client) -> None:
    client, session = api_client
    tid = _tid()
    user, budget = await create_user_with_budget(session, telegram_id=tid)
    await _seed(session, user, budget)
    h = auth_headers(tid)
    r = await client.get(HIST, params=_params(currency="UZS", limit=2), headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["total_count"] == 3 and len(body["items"]) == 2
    assert {i["currency"] for i in body["items"]} == {"UZS"}
    r2 = await client.get(HIST, params=_params(currency="UZS", limit=2, offset=2), headers=h)
    assert len(r2.json()["items"]) == 1
    r3 = await client.get(HIST, params=_params(currency="USD"), headers=h)
    assert r3.json()["total_count"] == 2
    assert {i["currency"] for i in r3.json()["items"]} == {"USD"}


async def test_history_without_currency_unchanged(api_client) -> None:
    client, session = api_client
    tid = _tid()
    user, budget = await create_user_with_budget(session, telegram_id=tid)
    await _seed(session, user, budget)
    r = await client.get(HIST, params=_params(), headers=auth_headers(tid))
    assert r.json()["total_count"] == 5


async def test_history_bad_currency_is_422(api_client) -> None:
    client, session = api_client
    tid = _tid()
    await create_user_with_budget(session, telegram_id=tid)
    r = await client.get(HIST, params=_params(currency="EUR"), headers=auth_headers(tid))
    assert r.status_code == 422


async def test_history_currency_keeps_personal_wallet_hidden(api_client) -> None:
    client, session = api_client
    tid = _tid()
    owner, budget = await create_user_with_budget(session, telegram_id=tid)
    member, _ = await create_user_with_budget(
        session, telegram_id=tid + 1, role="member", family_budget_id=budget.id
    )
    personal = Wallet(
        family_budget_id=budget.id, name="P", currency="UZS",
        is_personal=True, owner_user_id=owner.id,
    )
    session.add(personal)
    await session.flush()
    session.add(
        Transaction(
            family_budget_id=budget.id, type="expense", wallet_id=personal.id, amount=5,
            created_by_user_id=owner.id, transaction_date=datetime.now(UTC),
        )
    )
    await session.flush()
    r = await client.get(HIST, params=_params(currency="UZS"), headers=auth_headers(tid + 1))
    assert r.json()["total_count"] == 0
    r = await client.get(HIST, params=_params(currency="UZS"), headers=auth_headers(tid))
    assert r.json()["total_count"] == 1


async def _income(session, user, budget, *, is_demo=False):
    w = Wallet(family_budget_id=budget.id, name="W", currency="UZS")
    c = IncomeCategory(family_budget_id=budget.id, name="Salary")
    session.add_all([w, c])
    await session.flush()
    t = Transaction(
        family_budget_id=budget.id, type="income", wallet_id=w.id, amount=100,
        income_category_id=c.id, created_by_user_id=user.id,
        transaction_date=datetime.now(UTC), is_demo=is_demo,
    )
    session.add(t)
    await session.flush()
    return t


async def test_onboarding_step2_follows_income(api_client) -> None:
    client, session = api_client
    tid = _tid()
    user, budget = await create_user_with_budget(session, telegram_id=tid)
    h = auth_headers(tid)
    assert (await client.get(ONB, headers=h)).json()["steps"]["default_wallet_checked"] is False
    await _seed(session, user, budget)  # expenses only
    assert (await client.get(ONB, headers=h)).json()["steps"]["default_wallet_checked"] is False
    await _income(session, user, budget, is_demo=True)  # demo ignored
    assert (await client.get(ONB, headers=h)).json()["steps"]["default_wallet_checked"] is False
    t = await _income(session, user, budget)
    assert (await client.get(ONB, headers=h)).json()["steps"]["default_wallet_checked"] is True
    t.is_deleted = True
    await session.flush()
    assert (await client.get(ONB, headers=h)).json()["steps"]["default_wallet_checked"] is False
