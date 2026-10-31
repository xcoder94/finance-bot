"""m3-4b: the bot completes a waiting purchase from a photo / voice / text sum.

Real aiogram Dispatcher + Update + Bot objects into the real handlers, real
Postgres. Replaced at the outer boundary only: the AI parser (override), the
Telegram network (Bot.__call__ recorder) and the parser provider/key strings.
"""

from __future__ import annotations

import io
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.methods import SendMessage
from aiogram.types import File, Update
from sqlalchemy import func, select, update

from app.models.shopping import ShoppingItem, ShoppingPurchase
from app.models.transaction import Transaction
from app.parsing.stub import StubParser
from app.parsing.types import ParseRequest, ParseResponse, ParsedOperation
from app.services.shopping import create_pending_purchase
from bot.quick_entry import receipt_photo
from bot.quick_entry.handlers import router as quick_entry_router
from bot.quick_entry.handlers import set_parser_override
from bot.quick_entry.receipt_photo import (
    disabled_router,
    set_receipt_parser_override,
)
from bot.quick_entry.receipt_photo import router as receipt_router
from tests.test_quick_entry_flow import (
    SessionFactory,
    create_user,
    make_wallet,
    pytestmark,  # noqa: F401
    rollback_session,
)
from app.models.expense_category import ExpenseCategory


class FakeBot(Bot):
    def __init__(self) -> None:
        super().__init__(token="123456:TESTTOKEN")
        self.sent: list[SendMessage] = []

    async def __call__(self, method: Any, request_timeout: Any = None) -> Any:
        if isinstance(method, SendMessage):
            self.sent.append(method)
            return None
        if method.__api_method__ == "getFile":
            return File(file_id="f", file_unique_id="u", file_size=5, file_path="x.bin")
        return True

    async def download_file(self, *_a: Any, **_k: Any) -> io.BytesIO:  # type: ignore[override]
        return io.BytesIO(b"bytes")


def _update(telegram_id: int, **content: Any) -> Update:
    return Update.model_validate(
        {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "date": int(time.time()),
                "chat": {"id": 42, "type": "private"},
                "from": {"id": telegram_id, "is_bot": False, "first_name": "T"},
                **content,
            },
        }
    )


PHOTO = {"photo": [{"file_id": "f", "file_unique_id": "u", "width": 1, "height": 1}]}
VOICE = {"voice": {"file_id": "f", "file_unique_id": "u", "duration": 1}}


@pytest.fixture(autouse=True)
def _env(monkeypatch) -> Any:
    set_parser_override(None)
    set_receipt_parser_override(None)
    monkeypatch.setattr("app.config.RECEIPT_PHOTO_ENABLED", "true")
    monkeypatch.setattr("bot.quick_entry.handlers.PARSER_PROVIDER", "google")
    monkeypatch.setattr("bot.quick_entry.handlers.PARSER_API_KEY", "test-not-real")
    monkeypatch.setattr("bot.quick_entry.receipt_photo.PARSER_PROVIDER", "google")
    monkeypatch.setattr("bot.quick_entry.receipt_photo.PARSER_API_KEY", "test-not-real")
    monkeypatch.setattr("app.config.MINI_APP_URL", "https://app.example/")
    yield
    set_parser_override(None)
    set_receipt_parser_override(None)


def _wire(monkeypatch, session) -> None:
    factory = SessionFactory(session)
    monkeypatch.setattr("bot.quick_entry.handlers.async_session_factory", factory)
    monkeypatch.setattr("bot.quick_entry.receipt_photo.async_session_factory", factory)


async def feed(monkeypatch, session, telegram_id: int, flag_on: bool = True, **content) -> FakeBot:
    _wire(monkeypatch, session)
    bot = FakeBot()
    dp = Dispatcher()
    dp.include_router(quick_entry_router)
    dp.include_router(receipt_router if flag_on else disabled_router)
    try:
        await dp.feed_update(bot, _update(telegram_id, **content))
    finally:
        quick_entry_router._parent_router = None
        receipt_router._parent_router = None
        disabled_router._parent_router = None
    return bot


def expense(amount: int, *, category=None, comment=None, type_="expense") -> ParsedOperation:
    return ParsedOperation(
        type=type_, amount=amount, currency="UZS", wallet_hint=None,
        category=category, comment=comment,
    )


class FixedParser:
    def __init__(self, response: ParseResponse) -> None:
        self.response = response
        self.calls: list[ParseRequest] = []

    async def parse(self, request: ParseRequest) -> ParseResponse:
        self.calls.append(request)
        return self.response


async def setup_family(session, telegram_id: int, items=("молоко", "хлеб")):
    user, budget = await create_user(session, telegram_id=telegram_id)
    wallet = make_wallet(budget, name="Карта сум")
    food = ExpenseCategory(family_budget_id=budget.id, name="Еда", translation_key="food")
    session.add_all([wallet, food])
    await session.flush()
    session.add(
        ExpenseCategory(
            family_budget_id=budget.id, name="Продукты", translation_key="groceries",
            parent_id=food.id,
        )
    )
    user.default_wallet_id = wallet.id
    ids = []
    for name in items:
        item = ShoppingItem(
            family_budget_id=budget.id, name=name, added_by_user_id=user.id,
            created_at=datetime.now(UTC),
        )
        session.add(item)
        await session.flush()
        ids.append(item.id)
    return user, budget, ids


async def open_pending(session, user, ids, method):
    purchase, _ = await create_pending_purchase(
        session, user, item_ids=ids, method=method, client_token=None
    )
    return purchase


async def tx_count(session) -> int:
    return await session.scalar(select(func.count()).select_from(Transaction))


def launcher_url(sent: SendMessage) -> str:
    return sent.reply_markup.inline_keyboard[0][0].web_app.url


class TestPhoto:
    async def test_receipt_total_completes_purchase(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_350_001)
            purchase = await open_pending(session, user, ids, "receipt")
            parser = FixedParser(ParseResponse(operations=[expense(412_000)], receipt_status="ok"))
            set_receipt_parser_override(parser)

            bot = await feed(monkeypatch, session, user.telegram_id, **PHOTO)

            assert await tx_count(session) == 1
            tx = await session.scalar(select(Transaction))
            assert tx.amount == 412_000 and tx.type == "expense"
            assert tx.comment == "молоко, хлеб"  # items, not the shop
            assert await session.scalar(select(func.count()).select_from(ShoppingItem)) == 0
            await session.refresh(purchase)
            assert purchase.status == "completed" and purchase.method == "photo"
            assert purchase.transaction_id == tx.id
            assert len(bot.sent) == 1
            sent = bot.sent[0]
            assert sent.text == "Записал закупку: 412 000 сум."
            assert launcher_url(sent) == f"https://app.example/shopping/trip?purchase={purchase.id}"
            assert sent.reply_markup.inline_keyboard[0][0].text == "Вернуться в приложение"
            assert len(parser.calls) == 1 and parser.calls[0].image_base64
            await session.refresh(budget)
            assert budget.daily_model_calls == 1

    async def test_second_photo_does_not_make_a_second_operation(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_350_002)
            await open_pending(session, user, ids, "receipt")
            set_receipt_parser_override(
                FixedParser(ParseResponse(operations=[expense(412_000)], receipt_status="ok"))
            )
            await feed(monkeypatch, session, user.telegram_id, **PHOTO)
            await feed(monkeypatch, session, user.telegram_id, **PHOTO)
            # the second one is a regular receipt photo (quick entry), not a purchase
            rows = (await session.scalars(select(Transaction))).all()
            assert len(rows) == 2
            assert {t.comment for t in rows} == {"молоко, хлеб", None}
            purchases = (await session.scalars(select(ShoppingPurchase))).all()
            assert len(purchases) == 1 and purchases[0].status == "completed"

    async def test_unreadable_photo_marks_unrecognized_with_launcher(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_350_003)
            purchase = await open_pending(session, user, ids, "receipt")
            set_receipt_parser_override(
                FixedParser(ParseResponse(operations=[], receipt_status="unreadable"))
            )
            await session.execute(
                update(ShoppingPurchase)
                .where(ShoppingPurchase.id == purchase.id)
                .values(expires_at=datetime.now(UTC) + timedelta(minutes=2))
            )

            bot = await feed(monkeypatch, session, user.telegram_id, **PHOTO)

            await session.refresh(purchase)
            assert purchase.status == "unrecognized" and purchase.closed_at is None
            assert purchase.expires_at > datetime.now(UTC) + timedelta(minutes=29)
            assert await tx_count(session) == 0
            assert await session.scalar(select(func.count()).select_from(ShoppingItem)) == 2
            sent = bot.sent[0]
            assert sent.text == "Не разобрал сумму. Введите её в приложении вручную."
            assert launcher_url(sent).endswith(f"purchase={purchase.id}")
            await session.refresh(budget)
            assert budget.daily_unparsed == 1

    async def test_parser_outage_keeps_waiting(self, monkeypatch) -> None:
        from app.parsing.types import ParserUnavailable

        class Down:
            async def parse(self, request):
                raise ParserUnavailable("down")

        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_350_004)
            purchase = await open_pending(session, user, ids, "receipt")
            set_receipt_parser_override(Down())
            bot = await feed(monkeypatch, session, user.telegram_id, **PHOTO)
            await session.refresh(purchase)
            assert purchase.status == "awaiting"
            assert await tx_count(session) == 0
            await session.refresh(budget)
            assert budget.daily_model_calls == 0  # refunded

    async def test_photo_without_pending_keeps_old_behaviour(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_350_005)
            set_receipt_parser_override(
                FixedParser(ParseResponse(operations=[expense(30_000, category="Такси")], receipt_status="ok"))
            )
            bot = await feed(monkeypatch, session, user.telegram_id, **PHOTO)
            tx = await session.scalar(select(Transaction))
            assert tx.amount == 30_000 and tx.comment != "молоко, хлеб"
            assert "30 000 сум" in bot.sent[0].text
            assert await session.scalar(select(func.count()).select_from(ShoppingItem)) == 2

    async def test_photo_with_voice_pending_is_normal_quick_entry(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_350_006)
            purchase = await open_pending(session, user, ids, "voice")
            set_receipt_parser_override(
                FixedParser(ParseResponse(operations=[expense(30_000, category="Такси")], receipt_status="ok"))
            )
            await feed(monkeypatch, session, user.telegram_id, **PHOTO)
            await session.refresh(purchase)
            assert purchase.status == "awaiting"
            assert await session.scalar(select(func.count()).select_from(ShoppingItem)) == 2

    async def test_expired_pending_photo_goes_to_quick_entry(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_350_007)
            purchase = await open_pending(session, user, ids, "receipt")
            await session.execute(
                update(ShoppingPurchase)
                .where(ShoppingPurchase.id == purchase.id)
                .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
            set_receipt_parser_override(
                FixedParser(ParseResponse(operations=[expense(30_000, category="Такси")], receipt_status="ok"))
            )
            bot = await feed(monkeypatch, session, user.telegram_id, **PHOTO)
            await session.refresh(purchase)
            assert purchase.status == "expired"
            assert "30 000 сум" in bot.sent[0].text
            assert await session.scalar(select(func.count()).select_from(ShoppingItem)) == 2

    async def test_flag_off_photo_gets_old_answer_and_purchase_untouched(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_350_008)
            purchase = await open_pending(session, user, ids, "receipt")
            bot = await feed(monkeypatch, session, user.telegram_id, flag_on=False, **PHOTO)
            assert len(bot.sent) == 1 and "Не получилось записать" in bot.sent[0].text
            await session.refresh(purchase)
            assert purchase.status == "awaiting"
            assert await tx_count(session) == 0

    async def test_other_user_photo_does_not_touch_my_purchase(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_350_009)
            other, _ = await create_user(session, telegram_id=9_350_010, budget=budget)
            purchase = await open_pending(session, user, ids, "receipt")
            set_receipt_parser_override(
                FixedParser(ParseResponse(operations=[expense(30_000, category="Такси")], receipt_status="ok"))
            )
            await feed(monkeypatch, session, other.telegram_id, **PHOTO)
            await session.refresh(purchase)
            assert purchase.status == "awaiting"
            assert await session.scalar(select(func.count()).select_from(ShoppingItem)) == 2


class TestVoice:
    async def test_voice_sum_completes_purchase(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_351_001)
            purchase = await open_pending(session, user, ids, "voice")
            set_parser_override(
                FixedParser(
                    ParseResponse(
                        operations=[expense(412_000, type_="ambiguous")], speech_status="recognized"
                    )
                )
            )
            bot = await feed(monkeypatch, session, user.telegram_id, **VOICE)
            tx = await session.scalar(select(Transaction))
            assert tx.amount == 412_000 and tx.comment == "молоко, хлеб"
            await session.refresh(purchase)
            assert purchase.status == "completed" and purchase.method == "voice"
            assert bot.sent[0].text == "Записал закупку: 412 000 сум."
            assert launcher_url(bot.sent[0]).endswith(f"purchase={purchase.id}")
            assert await session.scalar(select(func.count()).select_from(ShoppingItem)) == 0

    async def test_voice_not_recognized_marks_unrecognized(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_351_002)
            purchase = await open_pending(session, user, ids, "voice")
            set_parser_override(
                FixedParser(ParseResponse(operations=[], speech_status="not_recognized"))
            )
            bot = await feed(monkeypatch, session, user.telegram_id, **VOICE)
            await session.refresh(purchase)
            assert purchase.status == "unrecognized"
            assert bot.sent[0].text == "Не разобрал сумму. Введите её в приложении вручную."
            assert launcher_url(bot.sent[0]).endswith(f"purchase={purchase.id}")
            assert await tx_count(session) == 0

    async def test_voice_without_amount_is_unrecognized(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_351_003)
            purchase = await open_pending(session, user, ids, "voice")
            set_parser_override(
                FixedParser(ParseResponse(operations=[], shopping_items=["сыр"], speech_status="recognized"))
            )
            await feed(monkeypatch, session, user.telegram_id, **VOICE)
            await session.refresh(purchase)
            assert purchase.status == "unrecognized"
            assert await session.scalar(select(func.count()).select_from(ShoppingItem)) == 2

    async def test_voice_without_pending_is_unchanged(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_351_004)
            set_parser_override(
                FixedParser(ParseResponse(operations=[expense(25_000, category="Такси")], speech_status="recognized"))
            )
            bot = await feed(monkeypatch, session, user.telegram_id, **VOICE)
            assert "25 000 сум" in bot.sent[0].text
            assert await session.scalar(select(func.count()).select_from(ShoppingItem)) == 2

    async def test_uzbek_user_gets_uzbek_reply(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_351_005)
            user.language = "uz"
            await open_pending(session, user, ids, "voice")
            set_parser_override(
                FixedParser(ParseResponse(operations=[expense(412_000, type_="ambiguous")], speech_status="recognized"))
            )
            bot = await feed(monkeypatch, session, user.telegram_id, **VOICE)
            assert bot.sent[0].text == "Xarid yozildi: 412 000 so'm."
            assert bot.sent[0].reply_markup.inline_keyboard[0][0].text == "Ilovaga qaytish"


class TestText:
    @pytest.mark.parametrize("method", ["receipt", "voice"])
    async def test_plain_number_completes_without_model_call(self, monkeypatch, method) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_352_001)
            purchase = await open_pending(session, user, ids, method)
            parser = FixedParser(ParseResponse(operations=[]))
            set_parser_override(parser)
            bot = await feed(monkeypatch, session, user.telegram_id, text="412000")
            tx = await session.scalar(select(Transaction))
            assert tx.amount == 412_000
            await session.refresh(purchase)
            assert purchase.status == "completed"
            assert purchase.method == ("photo" if method == "receipt" else "voice")
            assert bot.sent[0].text == "Записал закупку: 412 000 сум."
            assert parser.calls == []

    async def test_spoken_style_amount_via_model(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_352_002)
            purchase = await open_pending(session, user, ids, "voice")
            set_parser_override(
                FixedParser(ParseResponse(operations=[expense(412_000, type_="ambiguous")]))
            )
            bot = await feed(monkeypatch, session, user.telegram_id, text="четыреста двенадцать тысяч")
            await session.refresh(purchase)
            assert purchase.status == "completed"
            assert bot.sent[0].text == "Записал закупку: 412 000 сум."

    async def test_text_with_category_is_a_normal_expense(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_352_003)
            purchase = await open_pending(session, user, ids, "voice")
            set_parser_override(StubParser())  # "такси 25 тысяч" -> expense with category
            bot = await feed(monkeypatch, session, user.telegram_id, text="такси 25 тысяч")
            await session.refresh(purchase)
            assert purchase.status == "awaiting"
            assert "25 000 сум" in bot.sent[0].text
            assert await session.scalar(select(func.count()).select_from(ShoppingItem)) == 2

    async def test_number_without_pending_is_not_a_purchase(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_352_004)
            set_parser_override(FixedParser(ParseResponse(operations=[])))
            bot = await feed(monkeypatch, session, user.telegram_id, text="412000")
            assert await tx_count(session) == 0
            assert await session.scalar(select(func.count()).select_from(ShoppingItem)) == 2

    async def test_huge_number_is_not_accepted(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_352_005)
            purchase = await open_pending(session, user, ids, "voice")
            set_parser_override(FixedParser(ParseResponse(operations=[])))
            await feed(monkeypatch, session, user.telegram_id, text="99999999999999")
            await session.refresh(purchase)
            assert purchase.status != "completed"
            assert await tx_count(session) == 0

    async def test_manual_after_unrecognized_is_a_replay_safe_second_amount(self, monkeypatch) -> None:
        """Text sum on an already completed purchase makes no second operation."""
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_352_006)
            await open_pending(session, user, ids, "voice")
            set_parser_override(FixedParser(ParseResponse(operations=[])))
            await feed(monkeypatch, session, user.telegram_id, text="1000")
            await feed(monkeypatch, session, user.telegram_id, text="2000")
            assert await tx_count(session) == 1
