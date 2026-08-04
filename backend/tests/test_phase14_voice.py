"""Phase 14 — voice input (Google speech → shared quick-entry pipeline)."""

from __future__ import annotations

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
from app.parsing.stub import StubParser
from app.parsing.types import ParseResponse, ParsedOperation
from app.speech.base import SpeechUnavailable
from app.speech.factory import get_speech_client
from app.speech.google_client import GoogleSpeechClient
from bot.quick_entry.handlers import (
    handle_quick_entry_voice,
    set_parser_override,
    set_speech_client_override,
)
from bot.quick_entry.texts import MSG_NO_AMOUNT, MSG_VOICE_NOT_RECOGNIZED

MSG_VOICE_NOT_RECOGNIZED_EXPECTED = (
    "Не разобрал голосовое. Попробуйте записать ещё раз или напишите текстом."
)
SECRET_TRANSCRIPT = "СЕКРЕТНАЯ_РАСШИФРОВКА_такси_25_тысяч"


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


class StubSpeech:
    def __init__(self, text: str = "", *, exc: Exception | None = None) -> None:
        self.text = text
        self.exc = exc
        self.calls: list[bytes] = []

    async def transcribe(self, audio: bytes) -> str:
        self.calls.append(audio)
        if self.exc is not None:
            raise self.exc
        return self.text


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


@pytest.mark.anyio
async def test_google_speech_client_posts_ogg_and_returns_transcript() -> None:
    audio = b"fake-ogg-bytes"
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "results": [
                    {"alternatives": [{"transcript": "такси 25 тысяч"}]},
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    client = GoogleSpeechClient(api_key="test-key", model="env-model-name")
    with patch.object(client, "_http", httpx.AsyncClient(transport=transport)):
        text = await client.transcribe(audio)

    assert text == "такси 25 тысяч"
    assert "speech:recognize" in captured["url"]
    assert "key=test-key" in captured["url"]
    body = captured["body"]
    assert body["config"]["encoding"] == "OGG_OPUS"
    assert body["config"]["sampleRateHertz"] == 48000
    assert body["config"]["languageCode"] == "ru-RU"
    assert body["config"]["model"] == "env-model-name"
    assert body["audio"]["content"] == base64.b64encode(audio).decode()


@pytest.mark.anyio
async def test_google_speech_client_empty_results_returns_empty_string() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": []})

    client = GoogleSpeechClient(api_key="k", model="m")
    with patch.object(
        client, "_http", httpx.AsyncClient(transport=httpx.MockTransport(handler))
    ):
        assert await client.transcribe(b"x") == ""


@pytest.mark.anyio
async def test_google_speech_client_http_error_raises_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": {"message": "down"}})

    client = GoogleSpeechClient(api_key="k", model="m")
    with patch.object(
        client, "_http", httpx.AsyncClient(transport=httpx.MockTransport(handler))
    ):
        with pytest.raises(SpeechUnavailable):
            await client.transcribe(b"x")


def test_get_speech_client_inactive_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.speech.factory.SPEECH_API_KEY", None)
    monkeypatch.setattr("app.speech.factory.SPEECH_PROVIDER", None)
    monkeypatch.setattr("app.speech.factory.SPEECH_MODEL", None)
    client = get_speech_client()
    assert client.__class__.__name__ == "_InactiveSpeechClient"


def test_get_speech_client_google_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.speech.factory.SPEECH_API_KEY", "key")
    monkeypatch.setattr("app.speech.factory.SPEECH_PROVIDER", "google")
    monkeypatch.setattr("app.speech.factory.SPEECH_MODEL", "from-env")
    client = get_speech_client()
    assert isinstance(client, GoogleSpeechClient)


def test_get_speech_client_inactive_for_non_google_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.speech.factory.SPEECH_API_KEY", "key")
    monkeypatch.setattr("app.speech.factory.SPEECH_PROVIDER", "other")
    monkeypatch.setattr("app.speech.factory.SPEECH_MODEL", "m")
    client = get_speech_client()
    assert client.__class__.__name__ == "_InactiveSpeechClient"


def test_config_exposes_speech_env_vars() -> None:
    from app import config

    assert hasattr(config, "SPEECH_PROVIDER")
    assert hasattr(config, "SPEECH_API_KEY")
    assert hasattr(config, "SPEECH_MODEL")


def test_process_quick_entry_text_is_importable() -> None:
    from bot.quick_entry.handlers import process_quick_entry_text

    assert callable(process_quick_entry_text)


def test_msg_voice_not_recognized_constant() -> None:
    assert MSG_VOICE_NOT_RECOGNIZED == MSG_VOICE_NOT_RECOGNIZED_EXPECTED


@pytest.fixture(autouse=True)
def reset_speech_override() -> AsyncIterator[None]:
    set_speech_client_override(None)
    set_parser_override(None)
    yield
    set_speech_client_override(None)
    set_parser_override(None)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
class TestVoiceAcceptance:
    async def test_voice_sets_typing_indicator_immediately(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_014_001)
            await seed_taxi_setup(session, user, budget)

            transcript = "такси 25 тысяч"
            set_speech_client_override(StubSpeech(transcript))
            set_parser_override(
                StubParser(
                    responses={
                        transcript: ParseResponse(
                            operations=[
                                ParsedOperation(
                                    type="expense",
                                    amount=25_000,
                                    currency="UZS",
                                    wallet_hint=None,
                                    category="Такси",
                                    comment=None,
                                )
                            ]
                        )
                    }
                )
            )
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

    async def test_voice_transcribed_text_reaches_card_path(
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

            transcript = "такси 25000"
            set_speech_client_override(StubSpeech(transcript))
            set_parser_override(
                StubParser(
                    responses={
                        transcript: ParseResponse(
                            operations=[
                                ParsedOperation(
                                    type="expense",
                                    amount=25_000,
                                    currency="UZS",
                                    wallet_hint=None,
                                    category="Такси",
                                    comment=None,
                                )
                            ]
                        )
                    }
                )
            )
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )
            monkeypatch.setattr(
                "bot.quick_entry.handlers.resolve_operation_date",
                lambda _text, now=None: datetime(2026, 8, 1).date(),
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

            set_speech_client_override(StubSpeech(""))
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

    async def test_voice_no_amount_reuses_msg_no_amount(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_014_004)
            wallet = make_wallet(budget, name="Карта сум")
            session.add(wallet)
            user.default_wallet_id = wallet.id
            await session.flush()

            transcript = "просто такси"
            set_speech_client_override(StubSpeech(transcript))
            set_parser_override(
                StubParser(responses={transcript: ParseResponse(operations=[])})
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

            transcript = "три операции голосом"
            set_speech_client_override(StubSpeech(transcript))
            set_parser_override(
                StubParser(
                    responses={
                        transcript: ParseResponse(
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
                            ]
                        )
                    }
                )
            )
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

            assert message.answer.await_count == 3
            for call in message.answer.await_args_list:
                text = call.args[0]
                assert "➖" in text or "➕" in text
            await session.refresh(budget)
            assert budget.daily_model_calls == 1

    async def test_voice_reply_never_contains_transcription_string(
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

            set_speech_client_override(StubSpeech(SECRET_TRANSCRIPT))
            set_parser_override(
                StubParser(
                    responses={
                        SECRET_TRANSCRIPT: ParseResponse(
                            operations=[
                                ParsedOperation(
                                    type="expense",
                                    amount=15_000,
                                    currency="UZS",
                                    wallet_hint=None,
                                    category="Продукты",
                                    comment="на ужин",
                                )
                            ]
                        )
                    }
                )
            )
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            message = make_voice_message(telegram_id=user.telegram_id)
            bot = make_voice_bot()
            await handle_quick_entry_voice(message, bot)

            message.answer.assert_awaited_once()
            for call in message.answer.await_args_list:
                for part in _answer_text_parts(call):
                    assert SECRET_TRANSCRIPT not in part
