"""MVP 3 / m3-3: shopping list CRUD and one-sum purchase completion (real Postgres)."""

import asyncio
import socket
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_factory, engine, get_session
from app.main import app
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.shopping import ShoppingItem, ShoppingPurchase
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.transactions import MAX_AMOUNT
from tests.auth_helpers import TEST_APP_PASS_SECRET, bearer_header_for_telegram_id
from tests.db_helpers import db_address
from unittest.mock import AsyncMock, patch


def _db_available() -> bool:
    try:
        with socket.create_connection(db_address(), timeout=1):
            return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available"),
    pytest.mark.anyio,
]


def _tid() -> int:
    return int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000


def headers(telegram_id: int) -> dict[str, str]:
    return bearer_header_for_telegram_id(telegram_id)


@pytest.fixture
async def api_client() -> AsyncIterator[tuple[AsyncClient, AsyncSession]]:
    await engine.dispose()
    conn = await engine.connect()
    trans = await conn.begin()
    session = AsyncSession(
        bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )

    async def override() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override
    with patch("app.main.verify_postgres_connection", new=AsyncMock()):
        with patch("app.auth.deps.APP_PASS_SECRET", TEST_APP_PASS_SECRET):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                yield client, session
    await trans.rollback()
    await session.close()
    await conn.close()
    await engine.dispose()
    app.dependency_overrides.clear()


async def make_family(
    session: AsyncSession,
    *,
    with_categories: str = "full",  # full | food_only | none
    wallet_currency: str = "UZS",
    default_wallet: bool = True,
    second_member: bool = False,
) -> dict:
    budget = FamilyBudget(invite_token=f"t-{uuid.uuid4()}")
    session.add(budget)
    await session.flush()
    user = User(
        telegram_id=_tid(), family_budget_id=budget.id, role="owner", language="ru",
        first_name="Owner",
    )
    session.add(user)
    wallet = Wallet(
        family_budget_id=budget.id, name="Карта сум", currency=wallet_currency
    )
    session.add(wallet)
    await session.flush()
    if default_wallet:
        user.default_wallet_id = wallet.id
    other = None
    if second_member:
        other = User(
            telegram_id=_tid(), family_budget_id=budget.id, role="member",
            language="ru", first_name="Member",
        )
        session.add(other)
    food = groceries = None
    if with_categories in ("full", "food_only"):
        food = ExpenseCategory(
            family_budget_id=budget.id, name="Еда", translation_key="food"
        )
        session.add(food)
        await session.flush()
        if with_categories == "full":
            groceries = ExpenseCategory(
                family_budget_id=budget.id, name="Продукты",
                translation_key="groceries", parent_id=food.id,
            )
            session.add(groceries)
    await session.flush()
    return {
        "budget": budget, "user": user, "other": other, "wallet": wallet,
        "food": food, "groceries": groceries,
    }


async def add_items(client: AsyncClient, tid: int, *names: str) -> list[dict]:
    out = []
    for name in names:
        r = await client.post(
            "/api/v1/shopping/items", headers=headers(tid), json={"name": name}
        )
        assert r.status_code in (200, 201), r.text
        out.append(r.json())
    return out


async def buy(client, tid, item_ids, amount=50_000, token=None):
    return await client.post(
        "/api/v1/shopping/purchases",
        headers=headers(tid),
        json={
            "item_ids": [str(i) for i in item_ids],
            "amount": amount,
            "client_token": str(token or uuid.uuid4()),
        },
    )


class TestItemsCrud:
    async def test_add_list_rename_delete(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session)
        tid = fam["user"].telegram_id

        r = await client.post(
            "/api/v1/shopping/items", headers=headers(tid), json={"name": "  Молоко "}
        )
        assert r.status_code == 201, r.text
        item = r.json()
        assert item["name"] == "Молоко"
        assert set(item) == {"id", "name", "created_at"}

        r = await client.get("/api/v1/shopping/items", headers=headers(tid))
        assert r.status_code == 200
        assert [i["name"] for i in r.json()] == ["Молоко"]

        r = await client.patch(
            f"/api/v1/shopping/items/{item['id']}",
            headers=headers(tid), json={"name": "Кефир"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "Кефир"

        r = await client.delete(
            f"/api/v1/shopping/items/{item['id']}", headers=headers(tid)
        )
        assert r.status_code == 204
        r = await client.get("/api/v1/shopping/items", headers=headers(tid))
        assert r.json() == []
        count = await session.scalar(select(func.count()).select_from(ShoppingItem))
        assert count == 0  # hard delete, not soft

    async def test_list_ordered_by_created_at(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session)
        tid = fam["user"].telegram_id
        await add_items(client, tid, "b", "a", "c")
        r = await client.get("/api/v1/shopping/items", headers=headers(tid))
        assert [i["name"] for i in r.json()] == ["b", "a", "c"]

    @pytest.mark.parametrize("bad", ["", "   ", "x" * 61])
    async def test_invalid_names_rejected(self, api_client, bad) -> None:
        client, session = api_client
        fam = await make_family(session)
        r = await client.post(
            "/api/v1/shopping/items",
            headers=headers(fam["user"].telegram_id), json={"name": bad},
        )
        assert r.status_code == 422, r.text

    async def test_boundary_60_chars_and_emoji(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session)
        tid = fam["user"].telegram_id
        r = await client.post(
            "/api/v1/shopping/items", headers=headers(tid), json={"name": "я" * 60}
        )
        assert r.status_code == 201
        r = await client.post(
            "/api/v1/shopping/items", headers=headers(tid), json={"name": "🥛 молоко"}
        )
        assert r.status_code == 201
        assert r.json()["name"] == "🥛 молоко"

    async def test_inner_spaces_collapsed(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session)
        r = await client.post(
            "/api/v1/shopping/items",
            headers=headers(fam["user"].telegram_id),
            json={"name": "  зелёный   чай "},
        )
        assert r.json()["name"] == "зелёный чай"

    async def test_duplicate_case_insensitive_returns_existing(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session)
        tid = fam["user"].telegram_id
        first = (await add_items(client, tid, "Хлеб"))[0]
        r = await client.post(
            "/api/v1/shopping/items", headers=headers(tid), json={"name": "ХЛЕБ"}
        )
        assert r.status_code == 200, r.text
        assert r.json()["id"] == first["id"]
        assert r.json()["name"] == "Хлеб"
        count = await session.scalar(select(func.count()).select_from(ShoppingItem))
        assert count == 1

    async def test_rename_to_existing_name_conflicts(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session)
        tid = fam["user"].telegram_id
        a, b = await add_items(client, tid, "хлеб", "молоко")
        r = await client.patch(
            f"/api/v1/shopping/items/{b['id']}", headers=headers(tid),
            json={"name": "ХЛЕБ"},
        )
        assert r.status_code == 409
        assert r.json()["detail"] == "already_in_list"

    async def test_rename_own_name_with_other_case_ok(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session)
        tid = fam["user"].telegram_id
        (a,) = await add_items(client, tid, "хлеб")
        r = await client.patch(
            f"/api/v1/shopping/items/{a['id']}", headers=headers(tid),
            json={"name": "Хлеб"},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Хлеб"

    async def test_limit_101st_item_rejected(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session)
        tid = fam["user"].telegram_id
        for i in range(100):
            session.add(
                ShoppingItem(
                    family_budget_id=fam["budget"].id, name=f"item {i}",
                    added_by_user_id=fam["user"].id,
                )
            )
        await session.flush()
        r = await client.post(
            "/api/v1/shopping/items", headers=headers(tid), json={"name": "лишнее"}
        )
        assert r.status_code == 409, r.text
        assert r.json()["detail"] == "shopping_limit"
        # a duplicate of an existing item at the cap is still just "existing"
        r = await client.post(
            "/api/v1/shopping/items", headers=headers(tid), json={"name": "ITEM 5"}
        )
        assert r.status_code == 200

    async def test_members_of_one_family_share_the_list(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session, second_member=True)
        await add_items(client, fam["user"].telegram_id, "хлеб")
        r = await client.get(
            "/api/v1/shopping/items", headers=headers(fam["other"].telegram_id)
        )
        assert [i["name"] for i in r.json()] == ["хлеб"]
        other_item = r.json()[0]
        r = await client.delete(
            f"/api/v1/shopping/items/{other_item['id']}",
            headers=headers(fam["other"].telegram_id),
        )
        assert r.status_code == 204

    async def test_foreign_family_gets_404(self, api_client) -> None:
        client, session = api_client
        mine = await make_family(session)
        theirs = await make_family(session)
        (item,) = await add_items(client, theirs["user"].telegram_id, "чужое")
        tid = mine["user"].telegram_id
        r = await client.get("/api/v1/shopping/items", headers=headers(tid))
        assert r.json() == []
        r = await client.patch(
            f"/api/v1/shopping/items/{item['id']}", headers=headers(tid),
            json={"name": "моё"},
        )
        assert r.status_code == 404
        r = await client.delete(
            f"/api/v1/shopping/items/{item['id']}", headers=headers(tid)
        )
        assert r.status_code == 404
        r = await buy(client, tid, [item["id"]])
        assert r.status_code == 404
        # nothing happened to the other family's data
        r = await client.get(
            "/api/v1/shopping/items", headers=headers(theirs["user"].telegram_id)
        )
        assert [i["name"] for i in r.json()] == ["чужое"]
        assert await session.scalar(select(func.count()).select_from(Transaction)) == 0

    async def test_unauthenticated(self, api_client) -> None:
        client, _ = api_client
        assert (await client.get("/api/v1/shopping/items")).status_code in (401, 403)


class TestPurchase:
    async def test_three_items_two_checked(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session)
        tid = fam["user"].telegram_id
        milk, bread, eggs = await add_items(client, tid, "молоко", "хлеб", "яйца")

        r = await buy(client, tid, [milk["id"], eggs["id"]], amount=45_000)
        assert r.status_code == 201, r.text
        res = r.json()
        assert res["items_recorded"] == 2
        assert res["amount"] == 45_000
        assert res["currency"] == "UZS"
        assert res["category_label"] == "Еда · Продукты"
        assert res["wallet_name"] == "Карта сум"
        assert res["items_left"] == 1
        # income 0, expense 45 000 in the current month -> remaining = -45 000
        assert res["remaining"] == -45_000

        txns = (await session.scalars(select(Transaction))).all()
        assert len(txns) == 1
        t = txns[0]
        assert t.type == "expense" and t.amount == 45_000
        assert t.expense_category_id == fam["groceries"].id
        assert t.wallet_id == fam["wallet"].id
        assert t.created_by_user_id == fam["user"].id
        assert t.comment == "молоко, яйца"
        assert t.is_deleted is False

        left = await client.get("/api/v1/shopping/items", headers=headers(tid))
        assert [i["name"] for i in left.json()] == ["хлеб"]

        p = await session.scalar(select(ShoppingPurchase))
        assert p.status == "completed" and p.method == "manual"
        assert p.transaction_id == t.id
        assert sorted(p.bought_item_names) == ["молоко", "яйца"]
        assert p.closed_at is not None

    async def test_remaining_counts_income_and_matches_home_summary(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session)
        tid = fam["user"].telegram_id
        session.add(
            Transaction(
                family_budget_id=fam["budget"].id, type="income",
                wallet_id=fam["wallet"].id, amount=1_000_000,
                created_by_user_id=fam["user"].id,
                transaction_date=datetime.now(UTC),
            )
        )
        await session.flush()
        (a,) = await add_items(client, tid, "хлеб")
        res = (await buy(client, tid, [a["id"]], amount=30_000)).json()
        assert res["remaining"] == 970_000

    async def test_transaction_visible_in_history_and_editable(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session)
        tid = fam["user"].telegram_id
        (a,) = await add_items(client, tid, "хлеб")
        await buy(client, tid, [a["id"]], amount=10_000)
        t = await session.scalar(select(Transaction))
        r = await client.get(f"/api/v1/transactions/{t.id}", headers=headers(tid))
        assert r.status_code == 200
        r = await client.patch(
            f"/api/v1/transactions/{t.id}", headers=headers(tid),
            json={
                "transaction_date": datetime.now(UTC).isoformat(), "amount": 12_000,
                "wallet_id": str(fam["wallet"].id),
                "expense_category_id": str(fam["groceries"].id), "comment": "хлеб",
            },
        )
        assert r.status_code == 200, r.text

    async def test_get_purchase_result(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session, second_member=True)
        tid = fam["user"].telegram_id
        a, b = await add_items(client, tid, "хлеб", "соль")
        created = (await buy(client, tid, [a["id"]], amount=7_000)).json()
        r = await client.get(
            f"/api/v1/shopping/purchases/{created['id']}",
            headers=headers(fam["other"].telegram_id),
        )
        assert r.status_code == 200, r.text
        got = r.json()
        assert got["items_recorded"] == 1
        assert got["items_left"] == 1
        assert got["id"] == created["id"]
        assert got["amount"] == 7_000

    async def test_get_purchase_foreign_family_or_unknown_404(self, api_client) -> None:
        client, session = api_client
        mine = await make_family(session)
        theirs = await make_family(session)
        (a,) = await add_items(client, theirs["user"].telegram_id, "x")
        created = (await buy(client, theirs["user"].telegram_id, [a["id"]])).json()
        tid = mine["user"].telegram_id
        r = await client.get(
            f"/api/v1/shopping/purchases/{created['id']}", headers=headers(tid)
        )
        assert r.status_code == 404
        r = await client.get(
            f"/api/v1/shopping/purchases/{uuid.uuid4()}", headers=headers(tid)
        )
        assert r.status_code == 404

    async def test_category_falls_back_to_food_parent(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session, with_categories="food_only")
        tid = fam["user"].telegram_id
        (a,) = await add_items(client, tid, "хлеб")
        res = (await buy(client, tid, [a["id"]])).json()
        assert res["category_label"] == "Еда"
        t = await session.scalar(select(Transaction))
        assert t.expense_category_id == fam["food"].id

    async def test_category_falls_back_to_uncategorised(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session, with_categories="none")
        tid = fam["user"].telegram_id
        (a,) = await add_items(client, tid, "хлеб")
        res = (await buy(client, tid, [a["id"]])).json()
        assert res["category_label"] == "Без категории"
        t = await session.scalar(select(Transaction))
        assert t.expense_category_id is None

    async def test_renamed_groceries_found_by_seed_key(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session)
        fam["groceries"].name = "Магазин"
        await session.flush()
        (a,) = await add_items(client, fam["user"].telegram_id, "хлеб")
        res = (await buy(client, fam["user"].telegram_id, [a["id"]])).json()
        assert res["category_label"] == "Еда · Магазин"

    async def test_deleted_groceries_ignored(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session)
        fam["groceries"].is_deleted = True
        await session.flush()
        (a,) = await add_items(client, fam["user"].telegram_id, "хлеб")
        res = (await buy(client, fam["user"].telegram_id, [a["id"]])).json()
        assert res["category_label"] == "Еда"

    async def test_wallet_currency_is_used(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session, wallet_currency="USD")
        tid = fam["user"].telegram_id
        (a,) = await add_items(client, tid, "хлеб")
        res = (await buy(client, tid, [a["id"]], amount=20)).json()
        assert res["currency"] == "USD"

    async def test_no_default_wallet_falls_back_to_first_shared(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session, default_wallet=False)
        tid = fam["user"].telegram_id
        (a,) = await add_items(client, tid, "хлеб")
        res = (await buy(client, tid, [a["id"]])).json()
        assert res["wallet_name"] == "Карта сум"

    async def test_default_personal_wallet_of_someone_else_not_used(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session, second_member=True, default_wallet=False)
        await session.flush()
        personal = Wallet(
            family_budget_id=fam["budget"].id, name="Личный", currency="UZS",
            is_personal=True, owner_user_id=fam["other"].id,
        )
        session.add(personal)
        await session.flush()
        fam["user"].default_wallet_id = personal.id
        await session.flush()
        tid = fam["user"].telegram_id
        (a,) = await add_items(client, tid, "хлеб")
        res = (await buy(client, tid, [a["id"]])).json()
        assert res["wallet_name"] == "Карта сум"

    async def test_no_wallet_at_all_is_refused_without_side_effects(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session, default_wallet=False)
        fam["wallet"].is_deleted = True
        await session.flush()
        tid = fam["user"].telegram_id
        (a,) = await add_items(client, tid, "хлеб")
        r = await buy(client, tid, [a["id"]])
        assert r.status_code == 409
        assert r.json()["detail"] == "no_wallet"
        assert await session.scalar(select(func.count()).select_from(Transaction)) == 0
        left = await client.get("/api/v1/shopping/items", headers=headers(tid))
        assert len(left.json()) == 1

    async def test_comment_truncated_to_200(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session)
        tid = fam["user"].telegram_id
        ids = []
        for i in range(10):
            (it,) = await add_items(client, tid, f"{i}" + "ы" * 50)
            ids.append(it["id"])
        r = await buy(client, tid, ids)
        assert r.status_code == 201
        t = await session.scalar(select(Transaction))
        assert len(t.comment) == 200

    @pytest.mark.parametrize("amount", [0, -5, MAX_AMOUNT + 1])
    async def test_amount_bounds(self, api_client, amount) -> None:
        client, session = api_client
        fam = await make_family(session)
        tid = fam["user"].telegram_id
        (a,) = await add_items(client, tid, "хлеб")
        r = await buy(client, tid, [a["id"]], amount=amount)
        assert r.status_code == 422, r.text
        assert await session.scalar(select(func.count()).select_from(Transaction)) == 0

    async def test_amount_at_cap_accepted(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session)
        tid = fam["user"].telegram_id
        (a,) = await add_items(client, tid, "хлеб")
        r = await buy(client, tid, [a["id"]], amount=MAX_AMOUNT)
        assert r.status_code == 201, r.text

    async def test_empty_item_ids_rejected(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session)
        r = await buy(client, fam["user"].telegram_id, [])
        assert r.status_code == 422
        assert await session.scalar(select(func.count()).select_from(Transaction)) == 0

    async def test_more_than_100_item_ids_rejected(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session)
        r = await buy(client, fam["user"].telegram_id, [uuid.uuid4() for _ in range(101)])
        assert r.status_code == 422

    async def test_duplicate_ids_in_request_count_once(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session)
        tid = fam["user"].telegram_id
        (a,) = await add_items(client, tid, "хлеб")
        res = (await buy(client, tid, [a["id"], a["id"]])).json()
        assert res["items_recorded"] == 1

    async def test_items_already_bought_are_not_counted(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session, second_member=True)
        tid, other = fam["user"].telegram_id, fam["other"].telegram_id
        a, b = await add_items(client, tid, "хлеб", "соль")
        first = await buy(client, tid, [a["id"], b["id"]], amount=10_000)
        assert first.json()["items_recorded"] == 2
        # the second member bought "хлеб" too, from a stale screen: money was
        # spent, so the expense is still recorded, with 0 items (owner decision 5)
        second = await buy(client, other, [a["id"]], amount=5_000)
        assert second.status_code == 201, second.text
        assert second.json()["items_recorded"] == 0
        assert await session.scalar(select(func.count()).select_from(Transaction)) == 2

    async def test_retry_with_same_token_creates_nothing_new(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session)
        tid = fam["user"].telegram_id
        a, b = await add_items(client, tid, "хлеб", "соль")
        token = uuid.uuid4()
        first = await buy(client, tid, [a["id"]], amount=9_000, token=token)
        assert first.status_code == 201
        replay = await buy(client, tid, [a["id"]], amount=9_000, token=token)
        assert replay.status_code == 200, replay.text
        assert replay.json()["id"] == first.json()["id"]
        assert replay.json()["items_recorded"] == 1
        assert await session.scalar(select(func.count()).select_from(Transaction)) == 1
        assert await session.scalar(select(func.count()).select_from(ShoppingPurchase)) == 1

    async def test_token_is_required(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session)
        tid = fam["user"].telegram_id
        (a,) = await add_items(client, tid, "хлеб")
        r = await client.post(
            "/api/v1/shopping/purchases", headers=headers(tid),
            json={"item_ids": [a["id"]], "amount": 1000},
        )
        assert r.status_code == 422

    async def test_personal_wallet_purchase_hidden_from_shared_remaining(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session, default_wallet=False)
        personal = Wallet(
            family_budget_id=fam["budget"].id, name="Мой", currency="UZS",
            is_personal=True, owner_user_id=fam["user"].id,
        )
        session.add(personal)
        await session.flush()
        fam["user"].default_wallet_id = personal.id
        await session.flush()
        tid = fam["user"].telegram_id
        (a,) = await add_items(client, tid, "хлеб")
        res = (await buy(client, tid, [a["id"]], amount=1000)).json()
        assert res["wallet_name"] == "Мой"
        assert res["remaining"] == 0  # personal wallets are outside the shared summary


# ---------------------------------------------------------------------------
# Races: two real, committed sessions. No rollback fixture: each request runs
# in its own transaction, as in production.
# ---------------------------------------------------------------------------


@pytest.fixture
async def committed_family() -> AsyncIterator[dict]:
    await engine.dispose()
    async with async_session_factory() as s:
        fam = await make_family(s, second_member=True)
        await s.commit()
    ids = {
        "budget_id": fam["budget"].id,
        "tid": fam["user"].telegram_id,
        "other_tid": fam["other"].telegram_id,
        "user_id": fam["user"].id,
        "other_id": fam["other"].id,
    }
    yield ids
    async with async_session_factory() as s:
        bid = ids["budget_id"]
        await s.execute(delete(ShoppingPurchase).where(ShoppingPurchase.family_budget_id == bid))
        await s.execute(delete(Transaction).where(Transaction.family_budget_id == bid))
        await s.execute(delete(ShoppingItem).where(ShoppingItem.family_budget_id == bid))
        await s.execute(
            User.__table__.update().where(User.family_budget_id == bid).values(default_wallet_id=None)
        )
        await s.execute(delete(Wallet).where(Wallet.family_budget_id == bid))
        await s.execute(delete(ExpenseCategory).where(
            ExpenseCategory.family_budget_id == bid, ExpenseCategory.parent_id.is_not(None)))
        await s.execute(delete(ExpenseCategory).where(ExpenseCategory.family_budget_id == bid))
        await s.execute(delete(User).where(User.family_budget_id == bid))
        await s.execute(delete(FamilyBudget).where(FamilyBudget.id == bid))
        await s.commit()
    await engine.dispose()


@pytest.fixture
async def real_client() -> AsyncIterator[AsyncClient]:
    with patch("app.main.verify_postgres_connection", new=AsyncMock()):
        with patch("app.auth.deps.APP_PASS_SECRET", TEST_APP_PASS_SECRET):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                yield client


class TestRaces:
    async def test_same_purchase_completed_twice_in_parallel(
        self, committed_family, real_client
    ) -> None:
        fam = committed_family
        tid = fam["tid"]
        items = await add_items(real_client, tid, "молоко", "хлеб")
        token = uuid.uuid4()
        ids = [i["id"] for i in items]
        r1, r2 = await asyncio.gather(
            buy(real_client, tid, ids, amount=40_000, token=token),
            buy(real_client, tid, ids, amount=40_000, token=token),
        )
        assert sorted([r1.status_code, r2.status_code]) == [200, 201], (r1.text, r2.text)
        assert r1.json()["id"] == r2.json()["id"]
        assert r1.json()["items_recorded"] == r2.json()["items_recorded"] == 2
        async with async_session_factory() as s:
            bid = fam["budget_id"]
            assert await s.scalar(select(func.count()).select_from(Transaction).where(
                Transaction.family_budget_id == bid)) == 1
            assert await s.scalar(select(func.count()).select_from(ShoppingPurchase).where(
                ShoppingPurchase.family_budget_id == bid)) == 1
            assert await s.scalar(select(func.count()).select_from(ShoppingItem).where(
                ShoppingItem.family_budget_id == bid)) == 0

    async def test_two_members_share_an_item_it_is_written_off_once(
        self, committed_family, real_client
    ) -> None:
        fam = committed_family
        shared, mine, theirs = await add_items(real_client, fam["tid"], "хлеб", "мое", "их")
        r1, r2 = await asyncio.gather(
            buy(real_client, fam["tid"], [shared["id"], mine["id"]], amount=10_000),
            buy(real_client, fam["other_tid"], [shared["id"], theirs["id"]], amount=20_000),
        )
        assert r1.status_code == 201 and r2.status_code == 201, (r1.text, r2.text)
        recorded = sorted([r1.json()["items_recorded"], r2.json()["items_recorded"]])
        assert recorded == [1, 2]  # the shared item went to exactly one of them
        async with async_session_factory() as s:
            bid = fam["budget_id"]
            assert await s.scalar(select(func.count()).select_from(Transaction).where(
                Transaction.family_budget_id == bid)) == 2
            assert await s.scalar(select(func.count()).select_from(ShoppingItem).where(
                ShoppingItem.family_budget_id == bid)) == 0
            names = []
            for p in (await s.scalars(select(ShoppingPurchase).where(
                    ShoppingPurchase.family_budget_id == bid))).all():
                names += p.bought_item_names
            assert sorted(names) == sorted(["хлеб", "мое", "их"])

    async def test_parallel_adds_of_same_name_make_one_item(
        self, committed_family, real_client
    ) -> None:
        fam = committed_family
        rs = await asyncio.gather(*[
            real_client.post("/api/v1/shopping/items", headers=headers(fam["tid"]),
                             json={"name": "Хлеб" if i % 2 else "хлеб"})
            for i in range(6)
        ])
        assert all(r.status_code in (200, 201) for r in rs), [r.text for r in rs]
        assert len({r.json()["id"] for r in rs}) == 1
        async with async_session_factory() as s:
            assert await s.scalar(select(func.count()).select_from(ShoppingItem).where(
                ShoppingItem.family_budget_id == fam["budget_id"])) == 1
