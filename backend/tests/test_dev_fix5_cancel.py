"""dev-fix5: any way of giving the sum completes a waiting purchase; cancelling it."""

from __future__ import annotations

import time
import uuid
from typing import Any

import pytest
from aiogram import Dispatcher
from aiogram.types import Update
from sqlalchemy import func, select

from app.models.shopping import ShoppingItem, ShoppingPurchase
from app.models.transaction import Transaction
from app.parsing.types import ParseResponse
from bot.quick_entry.handlers import router as quick_entry_router
from bot.quick_entry.handlers import set_parser_override
from bot.quick_entry.receipt_photo import disabled_router, set_receipt_parser_override
from bot.quick_entry.receipt_photo import router as receipt_router
from tests.test_m3_4_bot_pending import (  # noqa: F401
    PHOTO,
    VOICE,
    FakeBot,
    FixedParser,
    _env,
    _wire,
    expense,
    feed,
    open_pending,
    setup_family,
    tx_count,
)
from tests.test_quick_entry_flow import pytestmark, rollback_session  # noqa: F401
from tests.test_shopping import api_client, headers  # noqa: F401
from tests.test_shopping_pending import (  # noqa: F401
    _flag_on_and_hint_recorder,
    create_pending,
    hints,
    two_items,
)


def cancel_update(telegram_id: int, purchase_id: Any) -> Update:
    return Update.model_validate(
        {
            "update_id": 1,
            "callback_query": {
                "id": "1",
                "chat_instance": "ci",
                "data": f"shp:cancel:{purchase_id}",
                "from": {"id": telegram_id, "is_bot": False, "first_name": "T"},
                "message": {
                    "message_id": 5,
                    "date": int(time.time()),
                    "chat": {"id": 42, "type": "private"},
                    "from": {"id": 1, "is_bot": True, "first_name": "B"},
                    "text": "x",
                },
            },
        }
    )


async def press_cancel(monkeypatch, session, telegram_id: int, purchase_id: Any) -> FakeBot:
    _wire(monkeypatch, session)
    bot = FakeBot()
    dp = Dispatcher()
    dp.include_router(quick_entry_router)
    dp.include_router(receipt_router)
    try:
        await dp.feed_update(bot, cancel_update(telegram_id, purchase_id))
    finally:
        quick_entry_router._parent_router = None
        receipt_router._parent_router = None
        disabled_router._parent_router = None
    return bot


def cancel_buttons(sent) -> list[str]:
    markup = sent.reply_markup
    if markup is None:
        return []
    return [
        b.callback_data
        for row in markup.inline_keyboard
        for b in row
        if b.callback_data
    ]


class TestAnyMethodAccepted:
    @pytest.mark.parametrize("selected", ["receipt", "voice"])
    async def test_text_sum_completes_whatever_method(self, monkeypatch, selected) -> None:
        async with rollback_session() as session:
            user, _b, ids = await setup_family(session, 9_360_001)
            p = await open_pending(session, user, ids, selected)
            await feed(monkeypatch, session, user.telegram_id, text="412000")
            await session.refresh(p)
            assert p.status == "completed"
            tx = await session.scalar(select(Transaction))
            assert tx.amount == 412_000 and tx.channel == "text"

    async def test_voice_sum_when_photo_selected(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, _b, ids = await setup_family(session, 9_360_002)
            p = await open_pending(session, user, ids, "receipt")
            set_parser_override(
                FixedParser(ParseResponse(operations=[expense(50_000)], speech_status="ok"))
            )
            await feed(monkeypatch, session, user.telegram_id, **VOICE)
            await session.refresh(p)
            assert p.status == "completed"
            tx = await session.scalar(select(Transaction))
            assert tx.amount == 50_000 and tx.channel == "voice"
            assert await session.scalar(select(func.count()).select_from(ShoppingItem)) == 0

    async def test_photo_sum_when_voice_selected(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, _b, ids = await setup_family(session, 9_360_003)
            p = await open_pending(session, user, ids, "voice")
            set_receipt_parser_override(
                FixedParser(ParseResponse(operations=[expense(412_000)], receipt_status="ok"))
            )
            await feed(monkeypatch, session, user.telegram_id, **PHOTO)
            await session.refresh(p)
            assert p.status == "completed"
            tx = await session.scalar(select(Transaction))
            assert tx.amount == 412_000 and tx.channel == "photo"


class TestBotCancelButton:
    async def test_not_recognized_has_cancel_button(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, _b, ids = await setup_family(session, 9_360_010)
            p = await open_pending(session, user, ids, "voice")
            bot = await feed(monkeypatch, session, user.telegram_id, text="12 3")
            assert cancel_buttons(bot.sent[-1]) == [f"shp:cancel:{p.id}"]

    async def test_press_cancels_and_keeps_items(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, _b, ids = await setup_family(session, 9_360_011)
            p = await open_pending(session, user, ids, "voice")
            bot = await press_cancel(monkeypatch, session, user.telegram_id, p.id)
            await session.refresh(p)
            assert p.status == "cancelled"
            assert await session.scalar(select(func.count()).select_from(ShoppingItem)) == 2
            assert await tx_count(session) == 0
            assert len(bot.sent) == 1 and "отмен" in bot.sent[0].text.lower()

    async def test_press_twice_is_harmless(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, _b, ids = await setup_family(session, 9_360_012)
            p = await open_pending(session, user, ids, "voice")
            await press_cancel(monkeypatch, session, user.telegram_id, p.id)
            await press_cancel(monkeypatch, session, user.telegram_id, p.id)
            await session.refresh(p)
            assert p.status == "cancelled" and await tx_count(session) == 0

    async def test_press_on_completed_does_not_cancel(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, _b, ids = await setup_family(session, 9_360_013)
            p = await open_pending(session, user, ids, "voice")
            await feed(monkeypatch, session, user.telegram_id, text="1000")
            await press_cancel(monkeypatch, session, user.telegram_id, p.id)
            await session.refresh(p)
            assert p.status == "completed" and await tx_count(session) == 1

    async def test_someone_elses_purchase_untouched(self, monkeypatch) -> None:
        async with rollback_session() as session:
            owner, _b, ids = await setup_family(session, 9_360_014)
            other, _b2, _ids2 = await setup_family(session, 9_360_015)
            p = await open_pending(session, owner, ids, "voice")
            await press_cancel(monkeypatch, session, other.telegram_id, p.id)
            await session.refresh(p)
            assert p.status == "awaiting"

    async def test_after_cancel_sum_is_quick_entry(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, _b, ids = await setup_family(session, 9_360_016)
            p = await open_pending(session, user, ids, "voice")
            await press_cancel(monkeypatch, session, user.telegram_id, p.id)
            set_parser_override(FixedParser(ParseResponse(operations=[expense(7_000)])))
            await feed(monkeypatch, session, user.telegram_id, text="7000 такси")
            await session.refresh(p)
            assert p.status == "cancelled"
            assert await session.scalar(select(func.count()).select_from(ShoppingItem)) == 2
            tx = await session.scalar(select(Transaction))
            assert tx.amount == 7_000


class TestHint:
    async def test_hint_universal_with_cancel_button(self, api_client, hints) -> None:
        client, session = api_client
        _fam, tid, ids = await two_items(client, session)
        for method in ("receipt", "voice"):
            r = await create_pending(client, tid, ids, method)
            assert r.status_code == 201
        texts = [t for _c, t in hints]
        assert texts == ["Пришлите сумму закупки: голосом, фото чека или текстом."] * 2

    async def test_hint_without_photo_when_disabled(self, api_client, hints, monkeypatch) -> None:
        client, session = api_client
        _fam, tid, ids = await two_items(client, session)
        monkeypatch.setattr("app.config.RECEIPT_PHOTO_ENABLED", "false")
        r = await create_pending(client, tid, ids, "voice")
        assert r.status_code == 201
        assert hints[-1][1] == "Пришлите сумму закупки: голосом или текстом."


class TestCancelApi:
    def url(self, pid) -> str:
        return f"/api/v1/shopping/purchases/{pid}/cancel"

    async def test_cancel_idempotent_keeps_items(self, api_client, hints) -> None:
        client, session = api_client
        _fam, tid, ids = await two_items(client, session)
        pid = (await create_pending(client, tid, ids, "voice")).json()["id"]
        r = await client.post(self.url(pid), headers=headers(tid))
        assert r.status_code == 200 and r.json()["status"] == "cancelled"
        r2 = await client.post(self.url(pid), headers=headers(tid))
        assert r2.status_code == 200 and r2.json()["status"] == "cancelled"
        assert await session.scalar(select(func.count()).select_from(ShoppingItem)) == 2
        assert await session.scalar(select(func.count()).select_from(Transaction)) == 0

    async def test_cancel_completed_is_410(self, api_client, hints) -> None:
        client, session = api_client
        _fam, tid, ids = await two_items(client, session)
        pid = (await create_pending(client, tid, ids, "voice")).json()["id"]
        done = await client.post(
            f"/api/v1/shopping/purchases/pending/{pid}/amount",
            headers=headers(tid),
            json={"amount": 1000},
        )
        assert done.status_code == 201, done.text
        r = await client.post(self.url(pid), headers=headers(tid))
        assert r.status_code == 410 and r.json()["detail"] == "purchase_closed"

    async def test_cancel_foreign_and_unknown_404(self, api_client, hints) -> None:
        client, session = api_client
        _fam, tid, ids = await two_items(client, session)
        pid = (await create_pending(client, tid, ids, "voice")).json()["id"]
        _fam2, tid2, _ids2 = await two_items(client, session)
        assert (await client.post(self.url(pid), headers=headers(tid2))).status_code == 404
        assert (await client.post(self.url(uuid.uuid4()), headers=headers(tid))).status_code == 404

    async def test_cancel_unrecognized(self, api_client, hints) -> None:
        client, session = api_client
        _fam, tid, ids = await two_items(client, session)
        pid = (await create_pending(client, tid, ids, "voice")).json()["id"]
        row = await session.get(ShoppingPurchase, uuid.UUID(pid))
        row.status = "unrecognized"
        await session.flush()
        r = await client.post(self.url(pid), headers=headers(tid))
        assert r.status_code == 200 and r.json()["status"] == "cancelled"
