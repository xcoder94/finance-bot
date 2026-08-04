"""Phase 14 — voice input (Google speech → shared quick-entry pipeline)."""

from __future__ import annotations

from datetime import date

import base64
import io
import json
import socket
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.income_category import IncomeCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.parsing.prompt import IMMUTABLE_PARSER_INSTRUCTIONS, build_mutable_parser_payload
from app.parsing.stub import StubParser
from app.parsing.types import ParseRequest, ParseResponse, ParsedOperation
from app.services.quick_entry_dates import apply_date_hint
from bot.quick_entry.handlers import (
    handle_quick_entry_voice,
    set_parser_override,
)
from bot.quick_entry.texts import MSG_MODEL_FAIL, MSG_NO_AMOUNT, MSG_VOICE_NOT_RECOGNIZED

MSG_VOICE_NOT_RECOGNIZED_EXPECTED = (
    "Не разобрал голосовое. Попробуйте записать ещё раз или напишите текстом."
)
SECRET_TRANSCRIPT = "СЕКРЕТНАЯ_РАСШИФРОВКА_такси_25_тысяч"
SECRET_AUDIO_LEAK = "SECRET_AUDIO_LEAK_MARKER"


class FixedParser:
    def __init__(self, response: ParseResponse) -> None:
        self.response = response
        self.calls: list[ParseRequest] = []

    async def parse(self, request: ParseRequest) -> ParseResponse:
        self.calls.append(request)
        return self.response


# --- Task 1 (phase 14b): types, prompt, date_hint ---


def test_parse_request_accepts_optional_audio_fields():
    req = ParseRequest(
        text="",
        wallet_names=[],
        expense_category_names=[],
        income_category_names=[],
        audio_base64="AAAA",
        audio_mime_type="audio/ogg",
    )
    assert req.audio_base64 == "AAAA"
    assert req.audio_mime_type == "audio/ogg"


def test_parse_response_accepts_speech_status_and_date_hint():
    r = ParseResponse(operations=[], speech_status="not_recognized", date_hint="2026-08-03")
    assert r.speech_status == "not_recognized"
    assert r.date_hint == "2026-08-03"


def test_mutable_payload_includes_today():
    req = ParseRequest(text="x", wallet_names=[], expense_category_names=[], income_category_names=[])
    payload = build_mutable_parser_payload(req)
    assert '"today"' in payload


def test_instructions_document_speech_status_and_date_hint():
    assert "speech_status" in IMMUTABLE_PARSER_INSTRUCTIONS
    assert "date_hint" in IMMUTABLE_PARSER_INSTRUCTIONS


def test_apply_date_hint_yesterday_iso():
    today = date(2026, 8, 4)
    assert apply_date_hint("2026-08-03", today) == date(2026, 8, 3)


def test_apply_date_hint_too_old_becomes_today():
    today = date(2026, 8, 4)
    assert apply_date_hint("2026-01-01", today) == today


def test_apply_date_hint_none_is_today():
    today = date(2026, 8, 4)
    assert apply_date_hint(None, today) == today


# --- Task 2 (phase 14b): HttpParser audio + speech_status ---


from app.parsing.http_adapter import HttpParser
from app.parsing.types import ParserMalformed, ParserUnavailable


@pytest.mark.anyio
async def test_http_parser_google_posts_inline_audio_part():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "operations": [
                                                {
                                                    "type": "expense",
                                                    "amount": 25000,
                                                    "currency": "UZS",
                                                    "wallet_hint": None,
                                                    "category": "Такси",
                                                    "comment": None,
                                                    "from_wallet_hint": None,
                                                    "to_wallet_hint": None,
                                                    "rate": None,
                                                }
                                            ],
                                            "speech_status": "recognized",
                                            "date_hint": None,
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        parser = HttpParser("google", "key", "env-model", client=client)
        resp = await parser.parse(
            ParseRequest(
                text="",
                wallet_names=["Карта"],
                expense_category_names=["Такси"],
                income_category_names=[],
                audio_base64="QQ==",
                audio_mime_type="audio/ogg",
            )
        )
    assert resp.speech_status == "recognized"
    parts = captured["body"]["contents"][0]["parts"]
    assert any("inlineData" in p or "inline_data" in p for p in parts)


@pytest.mark.anyio
async def test_http_parser_rejects_audio_when_not_google():
    parser = HttpParser("openai", "key", "m")
    with pytest.raises(ParserUnavailable):
        await parser.parse(
            ParseRequest(
                text="",
                wallet_names=[],
                expense_category_names=[],
                income_category_names=[],
                audio_base64="QQ==",
                audio_mime_type="audio/ogg",
            )
        )


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
    is_personal: bool = False,
    owner_user_id: uuid.UUID | None = None,
) -> Wallet:
    return Wallet(
        family_budget_id=budget.id,
        name=name,
        currency=currency,
        is_personal=is_personal,
        owner_user_id=owner_user_id,
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


async def seed_taxi_setup(
    session: AsyncSession, user: User, budget: FamilyBudget
) -> tuple[Wallet, ExpenseCategory]:
    wallet = make_wallet(budget, name="Наличный сум")
    transport = ExpenseCategory(family_budget_id=budget.id, name="Транспорт")
    session.add_all([wallet, transport])
    await session.flush()
    taxi = ExpenseCategory(
        family_budget_id=budget.id, name="Такси", parent_id=transport.id
    )
    session.add(taxi)
    user.default_wallet_id = wallet.id
    await session.flush()
    return wallet, taxi


def make_voice_message(*, telegram_id: int, chat_id: int = 42) -> SimpleNamespace:
    return SimpleNamespace(
        from_user=SimpleNamespace(id=telegram_id),
        chat=SimpleNamespace(id=chat_id),
        voice=SimpleNamespace(file_id="file-1"),
        text=None,
        answer=AsyncMock(),
    )


def make_voice_bot(*, audio: bytes = b"ogg-bytes") -> AsyncMock:
    bot = AsyncMock()
    bot.send_chat_action = AsyncMock()
    bot.get_file = AsyncMock(return_value=SimpleNamespace(file_path="voice.oga"))
    bio = io.BytesIO(audio)
    bot.download_file = AsyncMock(return_value=bio)
    return bot


def _answer_text_parts(call: object) -> list[str]:
    parts: list[str] = []
    args = call.args  # type: ignore[attr-defined]
    kwargs = call.kwargs  # type: ignore[attr-defined]
    if args:
        parts.append(str(args[0]))
    if "text" in kwargs:
        parts.append(str(kwargs["text"]))
    markup = kwargs.get("reply_markup")
    if markup is not None:
        parts.append(repr(markup))
    return parts


def test_config_has_no_speech_env_vars() -> None:
    from app import config

    assert not hasattr(config, "SPEECH_PROVIDER")
    assert not hasattr(config, "SPEECH_API_KEY")
    assert not hasattr(config, "SPEECH_MODEL")


def test_process_quick_entry_text_is_importable() -> None:
    from bot.quick_entry.handlers import process_quick_entry_text

    assert callable(process_quick_entry_text)


def test_msg_voice_not_recognized_constant() -> None:
    assert MSG_VOICE_NOT_RECOGNIZED == MSG_VOICE_NOT_RECOGNIZED_EXPECTED


@pytest.fixture(autouse=True)
def reset_parser_override() -> AsyncIterator[None]:
    set_parser_override(None)
    yield
    set_parser_override(None)


@pytest.fixture(autouse=True)
def parser_provider_google(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("bot.quick_entry.handlers.PARSER_PROVIDER", "google")
    monkeypatch.setattr("bot.quick_entry.handlers.PARSER_API_KEY", "test-key")


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
class TestVoiceAcceptance:
    async def test_voice_sets_typing_indicator_immediately(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_014_001)
            await seed_taxi_setup(session, user, budget)

            parser = FixedParser(
                ParseResponse(
                    operations=[
                        ParsedOperation(
                            type="expense",
                            amount=25_000,
                            currency="UZS",
                            wallet_hint=None,
                            category="Такси",
                            comment=None,
                        )
                    ],
                    speech_status="recognized",
                )
            )
            set_parser_override(parser)
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            call_order: list[str] = []
            message = make_voice_message(telegram_id=user.telegram_id)
            bot = make_voice_bot()

            async def track_typing(**_kwargs: object) -> None:
                call_order.append("typing")

            async def track_answer(*_args: object, **_kwargs: object) -> None:
                call_order.append("answer")

            bot.send_chat_action = AsyncMock(side_effect=track_typing)
            message.answer = AsyncMock(side_effect=track_answer)

            await handle_quick_entry_voice(message, bot)

            assert call_order[0] == "typing"
            assert "answer" in call_order
            assert call_order.index("typing") < call_order.index("answer")
            bot.send_chat_action.assert_awaited_with(
                chat_id=message.chat.id, action="typing"
            )

    async def test_voice_parsed_audio_reaches_card_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_014_002)
            wallet, _ = await seed_taxi_setup(session, user, budget)
            session.add(
                Transaction(
                    family_budget_id=budget.id,
                    type="income",
                    wallet_id=wallet.id,
                    amount=1_300_000,
                    created_by_user_id=user.id,
                    transaction_date=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
                )
            )
            await session.flush()

            set_parser_override(
                FixedParser(
                    ParseResponse(
                        operations=[
                            ParsedOperation(
                                type="expense",
                                amount=25_000,
                                currency="UZS",
                                wallet_hint=None,
                                category="Такси",
                                comment=None,
                            )
                        ],
                        speech_status="recognized",
                    )
                )
            )
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )
            monkeypatch.setattr(
                "bot.quick_entry.handlers.apply_date_hint",
                lambda _hint, today=None: datetime(2026, 8, 1).date(),
            )

            message = make_voice_message(telegram_id=user.telegram_id)
            bot = make_voice_bot()
            await handle_quick_entry_voice(message, bot)

            message.answer.assert_awaited_once()
            card_text = message.answer.await_args.args[0]
            assert "➖" in card_text and "25 000 сум" in card_text
            await session.refresh(budget)
            assert budget.daily_model_calls == 1

    async def test_voice_noise_returns_section9_text_and_spends_unparsed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_014_003)
            wallet = make_wallet(budget, name="Карта сум")
            session.add(wallet)
            user.default_wallet_id = wallet.id
            await session.flush()

            set_parser_override(
                FixedParser(
                    ParseResponse(
                        operations=[],
                        speech_status="not_recognized",
                    )
                )
            )
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            message = make_voice_message(telegram_id=user.telegram_id)
            bot = make_voice_bot()
            await handle_quick_entry_voice(message, bot)

            message.answer.assert_awaited_once_with(MSG_VOICE_NOT_RECOGNIZED)
            await session.refresh(budget)
            assert budget.daily_unparsed == 1
            assert budget.daily_model_calls == 0

    async def test_voice_provider_gate_returns_model_fail_without_unparsed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_014_007)
            wallet = make_wallet(budget, name="Карта сум")
            session.add(wallet)
            user.default_wallet_id = wallet.id
            await session.flush()

            monkeypatch.setattr("bot.quick_entry.handlers.PARSER_PROVIDER", "openai")
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            message = make_voice_message(telegram_id=user.telegram_id)
            bot = make_voice_bot()
            await handle_quick_entry_voice(message, bot)

            message.answer.assert_awaited_once_with(MSG_MODEL_FAIL)
            await session.refresh(budget)
            assert budget.daily_unparsed == 0
            assert budget.daily_model_calls == 0

    async def test_voice_missing_speech_status_returns_model_fail_without_counters(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_014_008)
            wallet = make_wallet(budget, name="Карта сум")
            session.add(wallet)
            user.default_wallet_id = wallet.id
            await session.flush()

            set_parser_override(
                FixedParser(
                    ParseResponse(
                        operations=[],
                        speech_status=None,
                    )
                )
            )
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            message = make_voice_message(telegram_id=user.telegram_id)
            bot = make_voice_bot()
            await handle_quick_entry_voice(message, bot)

            message.answer.assert_awaited_once_with(MSG_MODEL_FAIL)
            await session.refresh(budget)
            assert budget.daily_unparsed == 0
            assert budget.daily_model_calls == 0

    async def test_voice_missing_parser_api_key_returns_model_fail_without_counters(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_014_009)
            wallet = make_wallet(budget, name="Карта сум")
            session.add(wallet)
            user.default_wallet_id = wallet.id
            await session.flush()

            monkeypatch.setattr("bot.quick_entry.handlers.PARSER_PROVIDER", "google")
            monkeypatch.setattr("bot.quick_entry.handlers.PARSER_API_KEY", None)
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            message = make_voice_message(telegram_id=user.telegram_id)
            bot = make_voice_bot()
            await handle_quick_entry_voice(message, bot)

            message.answer.assert_awaited_once_with(MSG_MODEL_FAIL)
            await session.refresh(budget)
            assert budget.daily_unparsed == 0
            assert budget.daily_model_calls == 0

    async def test_voice_no_amount_reuses_msg_no_amount(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_014_004)
            wallet = make_wallet(budget, name="Карта сум")
            session.add(wallet)
            user.default_wallet_id = wallet.id
            await session.flush()

            set_parser_override(
                FixedParser(
                    ParseResponse(
                        operations=[],
                        speech_status="recognized",
                    )
                )
            )
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            message = make_voice_message(telegram_id=user.telegram_id)
            bot = make_voice_bot()
            await handle_quick_entry_voice(message, bot)

            message.answer.assert_awaited_once_with(MSG_NO_AMOUNT)
            await session.refresh(budget)
            assert budget.daily_unparsed == 1

    async def test_voice_three_operations_spend_one_model_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_014_005)
            wallet = make_wallet(budget, name="Карта сум")
            food = ExpenseCategory(family_budget_id=budget.id, name="Еда")
            session.add_all([wallet, food])
            await session.flush()
            groceries = ExpenseCategory(
                family_budget_id=budget.id, name="Продукты", parent_id=food.id
            )
            transport = ExpenseCategory(family_budget_id=budget.id, name="Транспорт")
            session.add_all([groceries, transport])
            await session.flush()
            taxi = ExpenseCategory(
                family_budget_id=budget.id, name="Такси", parent_id=transport.id
            )
            session.add(taxi)
            user.default_wallet_id = wallet.id
            await session.flush()

            parser = FixedParser(
                ParseResponse(
                    operations=[
                        ParsedOperation(
                            type="expense",
                            amount=10_000,
                            currency="UZS",
                            wallet_hint=None,
                            category="Продукты",
                            comment=None,
                        ),
                        ParsedOperation(
                            type="expense",
                            amount=5_000,
                            currency="UZS",
                            wallet_hint=None,
                            category="Такси",
                            comment=None,
                        ),
                        ParsedOperation(
                            type="income",
                            amount=50_000,
                            currency="UZS",
                            wallet_hint=None,
                            category="Зарплата",
                            comment=None,
                        ),
                    ],
                    speech_status="recognized",
                )
            )
            set_parser_override(parser)
            salary = IncomeCategory(family_budget_id=budget.id, name="Зарплата")
            session.add(salary)
            await session.flush()

            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            message = make_voice_message(telegram_id=user.telegram_id)
            bot = make_voice_bot()
            await handle_quick_entry_voice(message, bot)

            assert len(parser.calls) == 1
            assert message.answer.await_count == 3
            for call in message.answer.await_args_list:
                text = call.args[0]
                assert "➖" in text or "➕" in text
            await session.refresh(budget)
            assert budget.daily_model_calls == 1

    async def test_voice_reply_never_contains_audio_base64_or_transcript(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_014_006)
            wallet = make_wallet(budget, name="Карта сум")
            food = ExpenseCategory(family_budget_id=budget.id, name="Еда")
            session.add_all([wallet, food])
            await session.flush()
            groceries = ExpenseCategory(
                family_budget_id=budget.id, name="Продукты", parent_id=food.id
            )
            session.add(groceries)
            user.default_wallet_id = wallet.id
            await session.flush()

            audio = b"ogg-bytes-for-leak-test"
            audio_b64 = base64.b64encode(audio).decode()
            set_parser_override(
                FixedParser(
                    ParseResponse(
                        operations=[
                            ParsedOperation(
                                type="expense",
                                amount=15_000,
                                currency="UZS",
                                wallet_hint=None,
                                category="Продукты",
                                comment="на ужин",
                            )
                        ],
                        speech_status="recognized",
                    )
                )
            )
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            message = make_voice_message(telegram_id=user.telegram_id)
            bot = make_voice_bot(audio=audio)
            await handle_quick_entry_voice(message, bot)

            message.answer.assert_awaited_once()
            for call in message.answer.await_args_list:
                for part in _answer_text_parts(call):
                    assert audio_b64 not in part
                    assert SECRET_TRANSCRIPT not in part
                    assert SECRET_AUDIO_LEAK not in part
