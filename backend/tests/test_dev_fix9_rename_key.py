"""dev-fix9-r2: renaming keeps translation_key (permanent identity); shopping/remap still find it."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from tests.test_wallets_categories import (  # noqa: F401
    api_client,
    auth_headers,
    create_user_with_budget,
    pytestmark,
)
from app.models.expense_category import ExpenseCategory
from app.models.income_category import IncomeCategory
from app.models.wallet import Wallet
from app.parsing.prefilter import _matchable_terms, PrefilterCategory
from app.services.display_name import build_seed_name_by_key, display_name
from app.services.shopping import _resolve_category_id
from app.services.transaction_category_remap import remap_transaction_categories_to_budget


async def _setup(api_client):  # noqa: F811
    client, session = api_client
    user, budget = await create_user_with_budget(session, telegram_id=990901)
    return client, session, budget, auth_headers(990901)


async def test_wallet_rename_keeps_key(api_client) -> None:  # noqa: F811
    client, session, budget, h = await _setup(api_client)
    w = Wallet(family_budget_id=budget.id, name="Наличные", currency="UZS", translation_key="cash")
    session.add(w)
    await session.flush()
    r = await client.patch(f"/api/v1/wallets/{w.id}", headers=h, json={"name": "Кошелёк"})
    assert r.status_code == 200
    assert r.json()["name"] == "Кошелёк"
    assert r.json()["translation_key"] == "cash"
    got = [x for x in (await client.get("/api/v1/wallets", headers=h)).json() if x["id"] == str(w.id)]
    assert [(x["name"], x["translation_key"]) for x in got] == [("Кошелёк", "cash")]


async def test_income_category_rename_keeps_key(api_client) -> None:  # noqa: F811
    client, session, budget, h = await _setup(api_client)
    c = IncomeCategory(family_budget_id=budget.id, name="Зарплата", translation_key="salary")
    session.add(c)
    await session.flush()
    r = await client.patch(f"/api/v1/categories/income/{c.id}", headers=h, json={"name": "Оклад"})
    assert r.status_code == 200
    assert (r.json()["name"], r.json()["translation_key"]) == ("Оклад", "salary")


async def test_expense_category_rename_keeps_key(api_client) -> None:  # noqa: F811
    client, session, budget, h = await _setup(api_client)
    p = ExpenseCategory(family_budget_id=budget.id, name="Еда", translation_key="food")
    session.add(p)
    await session.flush()
    s = ExpenseCategory(
        family_budget_id=budget.id, name="Продукты", translation_key="groceries", parent_id=p.id
    )
    session.add(s)
    await session.flush()
    for obj, new, key in ((p, "Питание", "food"), (s, "Магазин", "groceries")):
        r = await client.patch(
            f"/api/v1/categories/expense/{obj.id}", headers=h, json={"name": new}
        )
        assert r.status_code == 200
        assert (r.json()["name"], r.json()["translation_key"]) == (new, key)


async def test_renamed_categories_still_found_by_shopping(api_client) -> None:  # noqa: F811
    client, session, budget, h = await _setup(api_client)
    p = ExpenseCategory(family_budget_id=budget.id, name="Еда", translation_key="food")
    session.add(p)
    await session.flush()
    s = ExpenseCategory(
        family_budget_id=budget.id, name="Продукты", translation_key="groceries", parent_id=p.id
    )
    session.add(s)
    await session.flush()
    await client.patch(f"/api/v1/categories/expense/{s.id}", headers=h, json={"name": "Магазин"})
    assert await _resolve_category_id(session, budget.id) == s.id
    # groceries gone -> falls back to renamed parent "food"
    s.is_deleted = True
    await client.patch(f"/api/v1/categories/expense/{p.id}", headers=h, json={"name": "Питание"})
    assert await _resolve_category_id(session, budget.id) == p.id


async def test_renamed_categories_still_found_by_remap(api_client) -> None:  # noqa: F811
    client, session, budget, h = await _setup(api_client)
    old_exp = ExpenseCategory(family_budget_id=budget.id, name="Еда", translation_key="food")
    old_inc = IncomeCategory(family_budget_id=budget.id, name="Зарплата", translation_key="salary")
    session.add_all([old_exp, old_inc])
    await session.flush()
    await client.patch(
        f"/api/v1/categories/expense/{old_exp.id}", headers=h, json={"name": "Питание"}
    )
    await client.patch(
        f"/api/v1/categories/income/{old_inc.id}", headers=h, json={"name": "Оклад"}
    )
    # target budget has the same seeded entities, both renamed differently
    _, target = await create_user_with_budget(session, telegram_id=990902)
    new_exp = ExpenseCategory(family_budget_id=target.id, name="Ресторан", translation_key="food")
    new_inc = IncomeCategory(family_budget_id=target.id, name="Доход", translation_key="salary")
    session.add_all([new_exp, new_inc])
    await session.flush()
    txn = SimpleNamespace(
        id=uuid.uuid4(), income_category_id=old_inc.id, expense_category_id=old_exp.id
    )
    await remap_transaction_categories_to_budget(session, [txn], target.id)
    assert txn.expense_category_id == new_exp.id
    assert txn.income_category_id == new_inc.id


def test_display_rule_renamed_shows_own_name() -> None:
    seeds = build_seed_name_by_key()
    assert display_name("Продукты", "groceries") == "Продукты"
    assert display_name("продукты", "groceries") == "Продукты"
    assert display_name("Магазин", "groceries") == "Магазин"
    assert display_name("Магазин", None) == "Магазин"
    # prefilter uses the same rule: renamed -> no seed cascade keywords
    renamed = PrefilterCategory(
        id=uuid.uuid4(), name="Магазин", translation_key="groceries", parent_id=None
    )
    assert _matchable_terms(renamed, seeds) == ["Магазин"]
