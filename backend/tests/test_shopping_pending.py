"""MVP 3 / m3-4b: purchase waiting for a sum from the bot (REST side), real Postgres."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from app.models.shopping import ShoppingItem, ShoppingPurchase
from app.models.transaction import Transaction
from tests.test_shopping import (  # noqa: F401  (fixtures + helpers + db marks)
    add_items,
    api_client,
    buy,
    headers,
    make_family,
    pytestmark,
)

BASE = "/api/v1/shopping/purchases/pending"


@pytest.fixture(autouse=True)
def _flag_on_and_hint_recorder(monkeypatch):
    """Photo flag ON by default; Telegram network replaced at the Bot boundary."""
    monkeypatch.setattr("app.config.RECEIPT_PHOTO_ENABLED", "true")
    sent: list[tuple[int, str]] = []

    class Recorder:
        class session:  # noqa: N801
            @staticmethod
            async def close() -> None:
                return None

        async def send_message(self, chat_id, text, **kwargs):
            sent.append((chat_id, text))

    async def fake_resolve(bot):
        return Recorder(), True

    monkeypatch.setattr("app.services.shopping_pending_notify.resolve_bot", fake_resolve)
    return sent


@pytest.fixture
def hints(_flag_on_and_hint_recorder):
    return _flag_on_and_hint_recorder


async def create_pending(client, tid, item_ids, method="receipt", **extra):
    return await client.post(
        BASE,
        headers=headers(tid),
        json={"item_ids": [str(i) for i in item_ids], "method": method, **extra},
    )


async def two_items(client, session):
    fam = await make_family(session)
    tid = fam["user"].telegram_id
    items = await add_items(client, tid, "молоко", "хлеб")
    return fam, tid, [i["id"] for i in items]


class TestCreate:
    async def test_creates_awaiting_and_hints_user(self, api_client, hints) -> None:
        client, session = api_client
        fam, tid, ids = await two_items(client, session)
        r = await create_pending(client, tid, ids, "receipt")
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["status"] == "awaiting" and body["method"] == "receipt"
        row = await session.get(ShoppingPurchase, uuid.UUID(body["id"]))
        assert row.method == "photo" and row.created_by_user_id == fam["user"].id
        delta = row.expires_at - datetime.now(UTC)
        assert timedelta(minutes=29) < delta <= timedelta(minutes=30)
        assert hints == [(tid, "Пришлите сумму закупки: голосом, фото чека или текстом.")]

    async def test_voice_hint_text(self, api_client, hints) -> None:
        client, session = api_client
        fam, tid, ids = await two_items(client, session)
        r = await create_pending(client, tid, ids, "voice")
        assert r.status_code == 201
        assert hints == [(tid, "Пришлите сумму закупки: голосом, фото чека или текстом.")]
        row = await session.get(ShoppingPurchase, uuid.UUID(r.json()["id"]))
        assert row.method == "voice"

    async def test_uzbek_user_gets_uzbek_hint(self, api_client, hints) -> None:
        client, session = api_client
        fam, tid, ids = await two_items(client, session)
        fam["user"].language = "uz"
        await session.flush()
        await create_pending(client, tid, ids, "voice")
        assert hints[0][1] == "Xarid summasini yuboring: ovozli xabar, chek rasmi yoki matn bilan."

    async def test_receipt_rejected_when_flag_off(self, api_client, hints, monkeypatch) -> None:
        client, session = api_client
        fam, tid, ids = await two_items(client, session)
        monkeypatch.setattr("app.config.RECEIPT_PHOTO_ENABLED", None)
        r = await create_pending(client, tid, ids, "receipt")
        assert r.status_code == 409 and r.json()["detail"] == "receipt_disabled"
        assert hints == []
        assert await session.scalar(select(func.count()).select_from(ShoppingPurchase)) == 0
        # voice is not affected by the photo flag
        assert (await create_pending(client, tid, ids, "voice")).status_code == 201

    @pytest.mark.parametrize(
        "payload",
        [
            {"item_ids": [], "method": "voice"},
            {"item_ids": ["x"], "method": "voice"},
            {"method": "voice"},
        ],
    )
    async def test_bad_input_422(self, api_client, hints, payload) -> None:
        client, session = api_client
        fam, tid, ids = await two_items(client, session)
        r = await client.post(BASE, headers=headers(tid), json=payload)
        assert r.status_code == 422

    async def test_unknown_method_and_extra_422(self, api_client, hints) -> None:
        client, session = api_client
        fam, tid, ids = await two_items(client, session)
        assert (await create_pending(client, tid, ids, "manual")).status_code == 422
        assert (await create_pending(client, tid, ids, "voice", zzz=1)).status_code == 422

    async def test_foreign_family_item_404(self, api_client, hints) -> None:
        client, session = api_client
        fam, tid, ids = await two_items(client, session)
        other = await make_family(session)
        theirs = await add_items(client, other["user"].telegram_id, "чужое")
        r = await create_pending(client, tid, [theirs[0]["id"]], "voice")
        assert r.status_code == 404
        assert hints == []

    async def test_new_pending_replaces_old(self, api_client, hints) -> None:
        client, session = api_client
        fam, tid, ids = await two_items(client, session)
        first = (await create_pending(client, tid, ids, "receipt")).json()
        second = (await create_pending(client, tid, ids, "voice")).json()
        assert first["id"] != second["id"]
        old = await session.get(ShoppingPurchase, uuid.UUID(first["id"]))
        await session.refresh(old)
        assert old.status == "cancelled" and old.closed_at is not None
        open_rows = await session.scalar(
            select(func.count())
            .select_from(ShoppingPurchase)
            .where(ShoppingPurchase.status.in_(("awaiting", "unrecognized")))
        )
        assert open_rows == 1

    async def test_replacing_an_expired_one_marks_it_expired(self, api_client, hints) -> None:
        client, session = api_client
        fam, tid, ids = await two_items(client, session)
        first = (await create_pending(client, tid, ids, "receipt")).json()
        await session.execute(
            update(ShoppingPurchase)
            .where(ShoppingPurchase.id == uuid.UUID(first["id"]))
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await create_pending(client, tid, ids, "receipt")
        old = await session.get(ShoppingPurchase, uuid.UUID(first["id"]))
        await session.refresh(old)
        assert old.status == "expired"

    async def test_client_token_retry_returns_same_row(self, api_client, hints) -> None:
        client, session = api_client
        fam, tid, ids = await two_items(client, session)
        token = str(uuid.uuid4())
        a = await create_pending(client, tid, ids, "receipt", client_token=token)
        b = await create_pending(client, tid, ids, "receipt", client_token=token)
        assert a.status_code == 201 and b.status_code == 200
        assert a.json()["id"] == b.json()["id"]
        assert len(hints) == 1  # no second hint for a replay

    async def test_requires_auth(self, api_client, hints) -> None:
        client, session = api_client
        r = await client.post(BASE, json={"item_ids": [str(uuid.uuid4())], "method": "voice"})
        assert r.status_code == 401


class TestStatus:
    async def test_awaiting_then_404_for_others(self, api_client, hints) -> None:
        client, session = api_client
        fam, tid, ids = await two_items(client, session)
        pid = (await create_pending(client, tid, ids, "receipt")).json()["id"]
        r = await client.get(f"{BASE}/{pid}", headers=headers(tid))
        assert r.status_code == 200
        assert r.json()["status"] == "awaiting" and r.json()["purchase_id"] is None
        other = await make_family(session)
        r = await client.get(f"{BASE}/{pid}", headers=headers(other["user"].telegram_id))
        assert r.status_code == 404
        r = await client.get(f"{BASE}/{uuid.uuid4()}", headers=headers(tid))
        assert r.status_code == 404

    async def test_same_family_other_member_gets_404(self, api_client, hints) -> None:
        client, session = api_client
        fam = await make_family(session, second_member=True)
        tid = fam["user"].telegram_id
        items = await add_items(client, tid, "a")
        pid = (await create_pending(client, tid, [items[0]["id"]], "voice")).json()["id"]
        r = await client.get(f"{BASE}/{pid}", headers=headers(fam["other"].telegram_id))
        assert r.status_code == 404

    async def test_lazy_expiry_on_read(self, api_client, hints) -> None:
        client, session = api_client
        fam, tid, ids = await two_items(client, session)
        pid = (await create_pending(client, tid, ids, "receipt")).json()["id"]
        await session.execute(
            update(ShoppingPurchase)
            .where(ShoppingPurchase.id == uuid.UUID(pid))
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        r = await client.get(f"{BASE}/{pid}", headers=headers(tid))
        assert r.json()["status"] == "expired"
        row = await session.get(ShoppingPurchase, uuid.UUID(pid))
        await session.refresh(row)
        assert row.status == "expired" and row.closed_at is not None

    async def test_unrecognized_status_visible(self, api_client, hints) -> None:
        client, session = api_client
        fam, tid, ids = await two_items(client, session)
        pid = (await create_pending(client, tid, ids, "receipt")).json()["id"]
        await session.execute(
            update(ShoppingPurchase)
            .where(ShoppingPurchase.id == uuid.UUID(pid))
            .values(status="unrecognized")
        )
        r = await client.get(f"{BASE}/{pid}", headers=headers(tid))
        assert r.json()["status"] == "unrecognized"


class TestManualAmount:
    async def test_completes_purchase_like_m3_3(self, api_client, hints) -> None:
        client, session = api_client
        fam, tid, ids = await two_items(client, session)
        extra = await add_items(client, tid, "яйца")  # not checked, stays
        pid = (await create_pending(client, tid, ids, "receipt")).json()["id"]
        r = await client.post(f"{BASE}/{pid}/amount", headers=headers(tid), json={"amount": 412_000})
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["id"] == pid and body["amount"] == 412_000
        assert body["items_recorded"] == 2 and body["items_left"] == 1
        assert body["category_label"] == "Еда · Продукты"
        tx = await session.get(Transaction, uuid.UUID(body["transaction_id"]))
        assert tx.type == "expense" and tx.amount == 412_000
        assert tx.comment == "молоко, хлеб"
        row = await session.get(ShoppingPurchase, uuid.UUID(pid))
        await session.refresh(row)
        assert row.status == "completed" and row.method == "manual"
        # status endpoint now points to the purchase
        st = (await client.get(f"{BASE}/{pid}", headers=headers(tid))).json()
        assert st["status"] == "completed" and st["purchase_id"] == pid
        # and the normal result endpoint works with the same id
        g = await client.get(f"/api/v1/shopping/purchases/{pid}", headers=headers(tid))
        assert g.status_code == 200 and g.json()["amount"] == 412_000
        assert extra

    async def test_repeat_amount_is_replay_no_second_operation(self, api_client, hints) -> None:
        client, session = api_client
        fam, tid, ids = await two_items(client, session)
        pid = (await create_pending(client, tid, ids, "voice")).json()["id"]
        a = await client.post(f"{BASE}/{pid}/amount", headers=headers(tid), json={"amount": 10_000})
        b = await client.post(f"{BASE}/{pid}/amount", headers=headers(tid), json={"amount": 99_999})
        assert a.status_code == 201 and b.status_code == 200
        assert b.json()["amount"] == 10_000
        assert b.json()["transaction_id"] == a.json()["transaction_id"]
        assert await session.scalar(select(func.count()).select_from(Transaction)) == 1

    @pytest.mark.parametrize("amount", [0, -5, 2_000_000_001, "abc", None, True])
    async def test_amount_bounds_422(self, api_client, hints, amount) -> None:
        client, session = api_client
        fam, tid, ids = await two_items(client, session)
        pid = (await create_pending(client, tid, ids, "voice")).json()["id"]
        r = await client.post(f"{BASE}/{pid}/amount", headers=headers(tid), json={"amount": amount})
        assert r.status_code == 422
        assert await session.scalar(select(func.count()).select_from(Transaction)) == 0

    async def test_foreign_and_unknown_id_404(self, api_client, hints) -> None:
        client, session = api_client
        fam, tid, ids = await two_items(client, session)
        pid = (await create_pending(client, tid, ids, "voice")).json()["id"]
        other = await make_family(session)
        r = await client.post(
            f"{BASE}/{pid}/amount", headers=headers(other["user"].telegram_id), json={"amount": 5}
        )
        assert r.status_code == 404
        r = await client.post(
            f"{BASE}/{uuid.uuid4()}/amount", headers=headers(tid), json={"amount": 5}
        )
        assert r.status_code == 404
        assert await session.scalar(select(func.count()).select_from(Transaction)) == 0

    async def test_cancelled_or_expired_is_410_without_operation(self, api_client, hints) -> None:
        client, session = api_client
        fam, tid, ids = await two_items(client, session)
        first = (await create_pending(client, tid, ids, "voice")).json()["id"]
        second = (await create_pending(client, tid, ids, "voice")).json()["id"]  # cancels first
        r = await client.post(f"{BASE}/{first}/amount", headers=headers(tid), json={"amount": 5})
        assert r.status_code == 410 and r.json()["detail"] == "purchase_closed"
        await session.execute(
            update(ShoppingPurchase)
            .where(ShoppingPurchase.id == uuid.UUID(second))
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        r = await client.post(f"{BASE}/{second}/amount", headers=headers(tid), json={"amount": 5})
        assert r.status_code == 410
        assert await session.scalar(select(func.count()).select_from(Transaction)) == 0
        assert await session.scalar(select(func.count()).select_from(ShoppingItem)) == 2

    async def test_manual_from_unrecognized_ok(self, api_client, hints) -> None:
        client, session = api_client
        fam, tid, ids = await two_items(client, session)
        pid = (await create_pending(client, tid, ids, "receipt")).json()["id"]
        await session.execute(
            update(ShoppingPurchase)
            .where(ShoppingPurchase.id == uuid.UUID(pid))
            .values(status="unrecognized")
        )
        r = await client.post(f"{BASE}/{pid}/amount", headers=headers(tid), json={"amount": 7_000})
        assert r.status_code == 201

    async def test_no_wallet_409_and_stays_open(self, api_client, hints) -> None:
        client, session = api_client
        fam = await make_family(session, default_wallet=False)
        tid = fam["user"].telegram_id
        items = await add_items(client, tid, "a")
        fam["wallet"].is_deleted = True
        await session.flush()
        pid = (await create_pending(client, tid, [items[0]["id"]], "voice")).json()["id"]
        r = await client.post(f"{BASE}/{pid}/amount", headers=headers(tid), json={"amount": 5})
        assert r.status_code == 409 and r.json()["detail"] == "no_wallet"
        row = await session.get(ShoppingPurchase, uuid.UUID(pid))
        await session.refresh(row)
        assert row.status == "awaiting"
        assert await session.scalar(select(func.count()).select_from(ShoppingItem)) == 1

    async def test_shared_item_bought_by_other_gives_zero_recorded(self, api_client, hints) -> None:
        client, session = api_client
        fam, tid, ids = await two_items(client, session)
        pid = (await create_pending(client, tid, ids, "voice")).json()["id"]
        # somebody else bought them via the normal path first
        assert (await buy(client, tid, ids, 1000)).status_code == 201
        r = await client.post(f"{BASE}/{pid}/amount", headers=headers(tid), json={"amount": 5_000})
        assert r.status_code == 201 and r.json()["items_recorded"] == 0  # owner decision p.5
        assert await session.scalar(select(func.count()).select_from(Transaction)) == 2


class TestFlagInMe:
    async def test_me_exposes_receipt_flag(self, api_client, hints, monkeypatch) -> None:
        from app.api.v1.me import _build_me_response

        client, session = api_client
        fam = await make_family(session)
        me = await _build_me_response(session, fam["user"])
        assert me.receipt_photo_enabled is True
        monkeypatch.setattr("app.config.RECEIPT_PHOTO_ENABLED", None)
        me = await _build_me_response(session, fam["user"])
        assert me.receipt_photo_enabled is False
