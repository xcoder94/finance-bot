"""Phase 16d — durable error logging."""

from __future__ import annotations

import logging
import socket
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

import app.logging_setup as logging_setup
from app.parsing.types import ParseResponse, ParserMalformed
from bot.quick_entry.handlers import handle_quick_entry_voice, set_parser_override
from bot.quick_entry.receipt_photo import (
    handle_receipt_photo,
    set_receipt_parser_override,
)
from tests.test_phase14_voice import make_voice_bot, make_voice_message
from tests.test_phase15_receipt_photo import (
    make_photo_bot,
    make_photo_message,
    seed_receipt_setup,
)
from tests.test_quick_entry_flow import (
    SessionFactory,
    create_user,
    make_wallet,
    rollback_session,
)


def _db_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            return True
    except OSError:
        return False


@pytest.fixture
def reset_logging_setup() -> AsyncIterator[None]:
    logging_setup._CONFIGURED = False
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    yield
    logging_setup._CONFIGURED = False
    for handler in root.handlers[:]:
        root.removeHandler(handler)


def test_setup_logging_writes_to_configured_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reset_logging_setup: None,
) -> None:
    log_file = tmp_path / "phase16d-test.log"
    monkeypatch.setattr("app.config.LOG_FILE_PATH", str(log_file))

    logging_setup.setup_logging()
    logging.getLogger("phase16d.test").error("durable log probe")

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "durable log probe" in content
    assert "ERROR" in content
    assert "phase16d.test" in content


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
class TestParserFailureLogging:
    @pytest.fixture(autouse=True)
    def reset_parser_override(self) -> AsyncIterator[None]:
        set_parser_override(None)
        set_receipt_parser_override(None)
        yield
        set_parser_override(None)
        set_receipt_parser_override(None)

    @pytest.fixture(autouse=True)
    def parser_provider_google(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("bot.quick_entry.handlers.PARSER_PROVIDER", "google")
        monkeypatch.setattr("bot.quick_entry.handlers.PARSER_API_KEY", "test-key")
        monkeypatch.setattr("bot.quick_entry.receipt_photo.PARSER_PROVIDER", "google")
        monkeypatch.setattr("bot.quick_entry.receipt_photo.PARSER_API_KEY", "test-key")

    async def test_voice_parser_failure_logged_with_context(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.ERROR, logger="bot.quick_entry.handlers")
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_016_101)
            wallet = make_wallet(budget, name="Карта сум")
            session.add(wallet)
            user.default_wallet_id = wallet.id
            await session.flush()

            class MalformedParser:
                async def parse(self, request: object) -> ParseResponse:
                    raise ParserMalformed("voice bad json")

            set_parser_override(MalformedParser())
            monkeypatch.setattr(
                "bot.quick_entry.handlers.async_session_factory",
                SessionFactory(session),
            )

            message = make_voice_message(telegram_id=user.telegram_id)
            bot = make_voice_bot()
            await handle_quick_entry_voice(message, bot)

            parser_logs = [
                r
                for r in caplog.records
                if r.name == "bot.quick_entry.handlers"
                and "entry_path=voice" in r.getMessage()
            ]
            assert len(parser_logs) == 1
            log_message = parser_logs[0].getMessage()
            assert str(user.family_budget_id) in log_message
            assert str(user.telegram_id) in log_message
            assert "voice bad json" in log_message

    async def test_receipt_parser_failure_logged_with_context(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.ERROR, logger="bot.quick_entry.receipt_photo")
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_016_102)
            await seed_receipt_setup(session, user, budget)

            class MalformedParser:
                async def parse(self, request: object) -> ParseResponse:
                    raise ParserMalformed("receipt bad json")

            set_receipt_parser_override(MalformedParser())
            monkeypatch.setattr(
                "bot.quick_entry.receipt_photo.async_session_factory",
                SessionFactory(session),
            )

            message = make_photo_message(telegram_id=user.telegram_id)
            bot = make_photo_bot()
            await handle_receipt_photo(message, bot)

            parser_logs = [
                r
                for r in caplog.records
                if r.name == "bot.quick_entry.receipt_photo"
                and "entry_path=receipt" in r.getMessage()
            ]
            assert len(parser_logs) == 1
            log_message = parser_logs[0].getMessage()
            assert str(user.family_budget_id) in log_message
            assert str(user.telegram_id) in log_message
            assert "receipt bad json" in log_message
