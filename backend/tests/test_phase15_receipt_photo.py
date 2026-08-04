"""Phase 15 — receipt photo."""

from __future__ import annotations

import io
import json
import socket
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime, UTC
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import receipt_photo_enabled
from app.db import engine
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.parsing.http_adapter import HttpParser
from app.parsing.prompt import IMMUTABLE_PARSER_INSTRUCTIONS
from app.parsing.types import (
    ParseRequest,
    ParseResponse,
    ParsedOperation,
    ParserMalformed,
    ParserUnavailable,
)
from bot.quick_entry.receipt_photo import (
    handle_receipt_photo,
    set_receipt_parser_override,
)
from bot.quick_entry.texts import MSG_MODEL_FAIL, MSG_RECEIPT_UNREADABLE

MSG_RECEIPT_UNREADABLE_EXPECTED = (
    "Не разобрал чек. Сфотографируйте его целиком при хорошем свете или запишите\n"
    "сумму текстом."
)


class FixedParser:
    def __init__(self, response: ParseResponse) -> None:
        self.response = response
        self.calls: list[ParseRequest] = []

    async def parse(self, request: ParseRequest) -> ParseResponse:
        self.calls.append(request)
        return self.response


def _db_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            return True
    except OSError:
        return False


async def _reset_engine() -> None:
    await engine.dispose()


@asynccontextmanager
async def rollback_session() -> AsyncIterator[AsyncSession]:
    await _reset_engine()
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await trans.rollback()
            await session.close()


async def create_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    role: str = "owner",
    budget: FamilyBudget | None = None,
) -> tuple[User, FamilyBudget]:
    if budget is None:
        budget = FamilyBudget(invite_token=f"test-{uuid.uuid4()}")
        session.add(budget)
        await session.flush()
    user = User(
        telegram_id=telegram_id,
        family_budget_id=budget.id,
        role=role,
        language="ru",
    )
    session.add(user)
    await session.flush()
    return user, budget


def make_wallet(
    budget: FamilyBudget,
    *,
    name: str,
    currency: str = "UZS",
) -> Wallet:
    return Wallet(
        family_budget_id=budget.id,
        name=name,
        currency=currency,
    )


class SessionFactory:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def __call__(self) -> SessionFactory:
        return self

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *_args: object) -> None:
        return None


async def seed_receipt_setup(
    session: AsyncSession, user: User, budget: FamilyBudget
) -> tuple[Wallet, Wallet, ExpenseCategory]:
    card = make_wallet(budget, name="Карта сум")
    cash = make_wallet(budget, name="Наличный сум")
    products = ExpenseCategory(family_budget_id=budget.id, name="Продукты")
    session.add_all([card, cash, products])
    user.default_wallet_id = card.id
    await session.flush()
    return card, cash, products


def make_photo_message(
    *, telegram_id: int, chat_id: int = 42, caption: str | None = None
) -> SimpleNamespace:
    return SimpleNamespace(
        from_user=SimpleNamespace(id=telegram_id),
        chat=SimpleNamespace(id=chat_id),
        photo=[
            SimpleNamespace(file_id="small"),
            SimpleNamespace(file_id="large"),
        ],
        caption=caption,
        answer=AsyncMock(),
    )


def make_photo_bot(*, image: bytes = b"jpeg-bytes") -> AsyncMock:
    bot = AsyncMock()
    bot.send_chat_action = AsyncMock()
    bot.get_file = AsyncMock(return_value=SimpleNamespace(file_path="photo.jpg"))
    bio = io.BytesIO(image)
    bot.download_file = AsyncMock(return_value=bio)
    return bot


@pytest.fixture(autouse=True)
def reset_receipt_parser_override() -> AsyncIterator[None]:
    set_receipt_parser_override(None)
    yield
    set_receipt_parser_override(None)


@pytest.fixture(autouse=True)
def receipt_parser_provider_google(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("bot.quick_entry.receipt_photo.PARSER_PROVIDER", "google")
    monkeypatch.setattr("bot.quick_entry.receipt_photo.PARSER_API_KEY", "test-key")


def test_parse_request_accepts_optional_image_fields():
    req = ParseRequest(
        text="",
        wallet_names=[],
        expense_category_names=[],
        income_category_names=[],
        image_base64="AAAA",
        image_mime_type="image/jpeg",
    )
    assert req.image_base64 == "AAAA"
    assert req.image_mime_type == "image/jpeg"


def test_parse_response_accepts_receipt_status():
    r = ParseResponse(operations=[], receipt_status="unreadable")
    assert r.receipt_status == "unreadable"


def test_msg_receipt_unreadable_exact_prd_text():
    assert MSG_RECEIPT_UNREADABLE == MSG_RECEIPT_UNREADABLE_EXPECTED


def test_instructions_document_receipt_status_and_rules():
    assert "receipt_status" in IMMUTABLE_PARSER_INSTRUCTIONS
    lowered = IMMUTABLE_PARSER_INSTRUCTIONS.lower()
    assert "total" in lowered or "итог" in lowered


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, False),
        ("", False),
        ("0", False),
        ("false", False),
        ("1", True),
        ("true", True),
        ("TRUE", True),
        ("yes", True),
        ("on", True),
    ],
)
def test_receipt_photo_enabled(monkeypatch: pytest.MonkeyPatch, value: str | None, expected: bool):
    monkeypatch.setattr("app.config.RECEIPT_PHOTO_ENABLED", value)
    assert receipt_photo_enabled() is expected


# --- Task 2: HttpParser image part + receipt_status + 20s timeout ---


def _google_receipt_response(receipt_status: str) -> dict:
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "operations": [],
                                    "receipt_status": receipt_status,
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }


@pytest.mark.anyio
async def test_http_parser_google_posts_inline_image_part():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json=_google_receipt_response("ok"))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        parser = HttpParser("google", "key", "env-model", client=client)
        resp = await parser.parse(
            ParseRequest(
                text="",
                wallet_names=[],
                expense_category_names=[],
                income_category_names=[],
                image_base64="QQ==",
                image_mime_type="image/jpeg",
            )
        )
    assert resp.receipt_status == "ok"
    parts = captured["body"]["contents"][0]["parts"]
    image_parts = [p for p in parts if "inlineData" in p]
    assert len(image_parts) == 1
    assert image_parts[0]["inlineData"]["mimeType"] == "image/jpeg"
    assert image_parts[0]["inlineData"]["data"] == "QQ=="


@pytest.mark.anyio
async def test_http_parser_rejects_image_when_not_google():
    parser = HttpParser("openai", "key", "m")
    with pytest.raises(ParserUnavailable):
        await parser.parse(
            ParseRequest(
                text="",
                wallet_names=[],
                expense_category_names=[],
                income_category_names=[],
                image_base64="QQ==",
                image_mime_type="image/jpeg",
            )
        )


@pytest.mark.anyio
async def test_http_parser_parses_receipt_status_unreadable():
    transport = httpx.MockTransport(
        lambda _r: httpx.Response(200, json=_google_receipt_response("unreadable"))
    )
    async with httpx.AsyncClient(transport=transport) as client:
        parser = HttpParser("google", "key", "m", client=client)
        resp = await parser.parse(
            ParseRequest(
                text="",
                wallet_names=[],
                expense_category_names=[],
                income_category_names=[],
                image_base64="QQ==",
                image_mime_type="image/jpeg",
            )
        )
    assert resp.receipt_status == "unreadable"


@pytest.mark.anyio
async def test_http_parser_invalid_receipt_status_raises_malformed():
    transport = httpx.MockTransport(
        lambda _r: httpx.Response(200, json=_google_receipt_response("maybe"))
    )
    async with httpx.AsyncClient(transport=transport) as client:
        parser = HttpParser("google", "key", "m", client=client)
        with pytest.raises(ParserMalformed):
            await parser.parse(
                ParseRequest(
                    text="",
                    wallet_names=[],
                    expense_category_names=[],
                    income_category_names=[],
                    image_base64="QQ==",
                    image_mime_type="image/jpeg",
                )
            )


@pytest.mark.anyio
async def test_http_parser_image_request_uses_20s_timeout():
    captured_timeouts: list[float] = []
    real_async_client = httpx.AsyncClient

    def mock_client_ctor(*args, **kwargs):
        if "timeout" in kwargs:
            captured_timeouts.append(kwargs["timeout"])
        transport = httpx.MockTransport(
            lambda _r: httpx.Response(200, json=_google_receipt_response("ok"))
        )
        return real_async_client(transport=transport, timeout=kwargs.get("timeout", 10))

    with patch("app.parsing.http_adapter.httpx.AsyncClient", side_effect=mock_client_ctor):
        parser = HttpParser("google", "key", "m")
        await parser.parse(
            ParseRequest(
                text="",
                wallet_names=[],
                expense_category_names=[],
                income_category_names=[],
                image_base64="QQ==",
                image_mime_type="image/jpeg",
            )
        )
    assert captured_timeouts == [20.0]


# --- Task 3: receipt_photo handler + main wiring ---


def test_register_bot_routers_skips_receipt_when_flag_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("bot.main.receipt_photo_enabled", lambda: False)
    included: list[object] = []

    class FakeDispatcher:
        def include_router(self, router: object) -> None:
            included.append(router)

    from bot.main import register_bot_routers
    from bot.quick_entry.receipt_photo import router as receipt_router

    register_bot_routers(FakeDispatcher())
    assert receipt_router not in included


def test_register_bot_routers_includes_receipt_when_flag_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("bot.main.receipt_photo_enabled", lambda: True)
    included: list[object] = []

    class FakeDispatcher:
        def include_router(self, router: object) -> None:
            included.append(router)

    from bot.main import register_bot_routers
    from bot.quick_entry.receipt_photo import router as receipt_router

    register_bot_routers(FakeDispatcher())
    assert receipt_router in included


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
class TestReceiptPhotoAcceptance:
    async def test_receipt_photo_creates_expense_card(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_015_001)
            card, _, _ = await seed_receipt_setup(session, user, budget)
            session.add(
                Transaction(
                    family_budget_id=budget.id,
                    type="income",
                    wallet_id=card.id,
                    amount=500_000,
                    created_by_user_id=user.id,
                    transaction_date=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
                )
            )
            await session.flush()

            set_receipt_parser_override(
                FixedParser(
                    ParseResponse(
                        operations=[
                            ParsedOperation(
                                type="expense",
                                amount=42_500,
                                currency="UZS",
                                wallet_hint=None,
                                category="Продукты",
                                comment="Магнит",
                            )
                        ],
                        receipt_status="ok",
                    )
                )
            )
            monkeypatch.setattr(
                "bot.quick_entry.receipt_photo.async_session_factory",
                SessionFactory(session),
            )

            message = make_photo_message(telegram_id=user.telegram_id)
            bot = make_photo_bot()
            await handle_receipt_photo(message, bot)

            message.answer.assert_awaited_once()
            card_text = message.answer.await_args.args[0]
            assert "➖" in card_text and "42 500 сум" in card_text
            assert "Продукты" in card_text
            assert "Магнит" in card_text
            assert "Карта сум" in card_text
            await session.refresh(budget)
            assert budget.daily_model_calls == 1

    async def test_receipt_caption_cash_wallet_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_015_002)
            card, cash, _ = await seed_receipt_setup(session, user, budget)
            await session.flush()

            set_receipt_parser_override(
                FixedParser(
                    ParseResponse(
                        operations=[
                            ParsedOperation(
                                type="expense",
                                amount=10_000,
                                currency="UZS",
                                wallet_hint="Карта сум",
                                category="Продукты",
                                comment="Магнит",
                            )
                        ],
                        receipt_status="ok",
                    )
                )
            )
            monkeypatch.setattr(
                "bot.quick_entry.receipt_photo.async_session_factory",
                SessionFactory(session),
            )

            message = make_photo_message(
                telegram_id=user.telegram_id, caption="с наличных"
            )
            bot = make_photo_bot()
            await handle_receipt_photo(message, bot)

            card_text = message.answer.await_args.args[0]
            assert "Наличный сум" in card_text
            assert "Карта сум" not in card_text.split("Осталось")[0]

    async def test_receipt_unreadable_returns_prd_text_and_spends_unparsed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_015_003)
            await seed_receipt_setup(session, user, budget)

            set_receipt_parser_override(
                FixedParser(
                    ParseResponse(
                        operations=[],
                        receipt_status="unreadable",
                    )
                )
            )
            monkeypatch.setattr(
                "bot.quick_entry.receipt_photo.async_session_factory",
                SessionFactory(session),
            )

            message = make_photo_message(telegram_id=user.telegram_id)
            bot = make_photo_bot()
            await handle_receipt_photo(message, bot)

            message.answer.assert_awaited_once_with(MSG_RECEIPT_UNREADABLE)
            txns = list(
                await session.scalars(
                    select(Transaction).where(
                        Transaction.family_budget_id == budget.id
                    )
                )
            )
            assert txns == []
            await session.refresh(budget)
            assert budget.daily_unparsed == 1
            assert budget.daily_model_calls == 1

    async def test_receipt_missing_receipt_status_returns_model_fail_without_counters(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_015_006)
            await seed_receipt_setup(session, user, budget)

            set_receipt_parser_override(
                FixedParser(
                    ParseResponse(
                        operations=[],
                        receipt_status=None,
                    )
                )
            )
            monkeypatch.setattr(
                "bot.quick_entry.receipt_photo.async_session_factory",
                SessionFactory(session),
            )

            message = make_photo_message(telegram_id=user.telegram_id)
            bot = make_photo_bot()
            await handle_receipt_photo(message, bot)

            message.answer.assert_awaited_once_with(MSG_MODEL_FAIL)
            await session.refresh(budget)
            assert budget.daily_unparsed == 0
            assert budget.daily_model_calls == 0

    async def test_receipt_old_date_hint_becomes_today(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_015_004)
            card, _, _ = await seed_receipt_setup(session, user, budget)
            await session.flush()

            fixed_today = date(2026, 8, 4)
            monkeypatch.setattr(
                "bot.quick_entry.receipt_photo.tashkent_today_for_counters",
                lambda: fixed_today,
            )
            set_receipt_parser_override(
                FixedParser(
                    ParseResponse(
                        operations=[
                            ParsedOperation(
                                type="expense",
                                amount=5_000,
                                currency="UZS",
                                wallet_hint=None,
                                category="Продукты",
                                comment="Магнит",
                            )
                        ],
                        receipt_status="ok",
                        date_hint="2026-01-01",
                    )
                )
            )
            monkeypatch.setattr(
                "bot.quick_entry.receipt_photo.async_session_factory",
                SessionFactory(session),
            )

            message = make_photo_message(telegram_id=user.telegram_id)
            bot = make_photo_bot()
            await handle_receipt_photo(message, bot)

            card_text = message.answer.await_args.args[0]
            assert "4 августа" in card_text
            txn = (
                await session.scalars(
                    select(Transaction).where(
                        Transaction.family_budget_id == budget.id,
                        Transaction.type == "expense",
                    )
                )
            ).one()
            assert txn.transaction_date.astimezone(UTC).date() == fixed_today

    async def test_receipt_album_three_photos_three_model_calls(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_015_005)
            await seed_receipt_setup(session, user, budget)

            parser = FixedParser(
                ParseResponse(
                    operations=[
                        ParsedOperation(
                            type="expense",
                            amount=1_000,
                            currency="UZS",
                            wallet_hint=None,
                            category="Продукты",
                            comment="Магнит",
                        )
                    ],
                    receipt_status="ok",
                )
            )
            set_receipt_parser_override(parser)
            monkeypatch.setattr(
                "bot.quick_entry.receipt_photo.async_session_factory",
                SessionFactory(session),
            )

            for _ in range(3):
                message = make_photo_message(telegram_id=user.telegram_id)
                bot = make_photo_bot()
                await handle_receipt_photo(message, bot)

            assert len(parser.calls) == 3
            await session.refresh(budget)
            assert budget.daily_model_calls == 3
            txns = list(
                await session.scalars(
                    select(Transaction).where(
                        Transaction.family_budget_id == budget.id,
                        Transaction.type == "expense",
                    )
                )
            )
            assert len(txns) == 3


# --- Task 4: flag-off isolation ---


def test_handlers_import_with_receipt_flag_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.RECEIPT_PHOTO_ENABLED", None)
    from bot.quick_entry import handlers  # noqa: F401

    assert handlers.router is not None


def test_voice_handler_import_with_receipt_flag_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.RECEIPT_PHOTO_ENABLED", None)
    from bot.quick_entry.handlers import handle_quick_entry_voice

    assert callable(handle_quick_entry_voice)


def test_receipt_photo_enabled_false_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.RECEIPT_PHOTO_ENABLED", None)
    assert receipt_photo_enabled() is False
