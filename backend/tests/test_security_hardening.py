"""Security hardening tests.

Covers:
  - Task 1: media must not be downloaded before the sender is authorised,
    and oversized media must never be downloaded.
  - Task 2: quick-entry amounts/rates are bounded and comments are truncated.
  - Task 3: daily counters are incremented atomically at the DB level.
  - Task 4: user-controlled values are Markdown-escaped before being sent.

No local PostgreSQL is available in this environment. Tests that would
otherwise need the app's Postgres-backed session use a fake in-memory
session (Tasks 1 and 2) or a real sqlite (via aiosqlite) engine driven
through the actual production code path (Task 3), never mocking the SQL
itself.
"""

from __future__ import annotations

import asyncio
import io
import tempfile
import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.models.base import Base
from app.models.family_budget import FamilyBudget
from app.parsing.types import ParsedOperation, ParseResponse
from app.services.quick_entry_counters import (
    ensure_counters_day,
    spend_model_call,
    spend_unparsed,
    tashkent_today_for_counters,
)
from bot.onboarding import MESSAGES
from bot.quick_entry.cards import escape_markdown, format_card
from bot.quick_entry.handlers import (
    MAX_VOICE_BYTES,
    _filter_countable,
    _is_ambiguous,
    _is_clear,
    _is_transfer_op,
    _process_parsed_response,
    _strip_op_comment,
    handle_quick_entry_voice,
)
from bot.quick_entry.receipt_photo import MAX_PHOTO_BYTES, handle_receipt_photo
from bot.quick_entry.texts import MSG_MODEL_FAIL, MSG_NO_AMOUNT

pytestmark = pytest.mark.anyio


# --------------------------------------------------------------------------
# Fakes shared across Task 1 / Task 2 tests (no real DB).
# --------------------------------------------------------------------------


class FakeResult:
    def __init__(self, rows: list = None):
        self._rows = rows or []

    def all(self):
        return self._rows


class FakeSession:
    """Stands in for AsyncSession without touching a real database.

    `get_map` resolves `session.get(Model, id)` calls; everything else that
    would normally run a query returns empty/no-op results, which is fine
    for the code paths under test here (they either return before reaching
    a real query, or the test asserts a helper was never called).
    """

    def __init__(self, get_map: dict | None = None):
        self._get_map = get_map or {}
        self.committed = False

    async def get(self, model, id_):
        return self._get_map.get((model, id_))

    async def execute(self, *_a, **_k):
        return SimpleNamespace(scalar_one=lambda: 0)

    async def refresh(self, _obj):
        return None

    async def commit(self):
        self.committed = True

    async def scalar(self, *_a, **_k):
        return None

    async def scalars(self, *_a, **_k):
        return FakeResult([])


class FakeSessionFactory:
    def __init__(self, session: FakeSession):
        self._session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *_a):
        return None


def make_message(*, telegram_id: int, chat_id: int = 1, voice=True):
    kwargs = dict(
        from_user=SimpleNamespace(id=telegram_id),
        chat=SimpleNamespace(id=chat_id),
        text=None,
        caption=None,
        answer=AsyncMock(),
    )
    if voice:
        kwargs["voice"] = SimpleNamespace(file_id="voice-1")
        kwargs["photo"] = None
    else:
        kwargs["voice"] = None
        kwargs["photo"] = [SimpleNamespace(file_id="photo-1")]
    return SimpleNamespace(**kwargs)


def make_bot(*, file_size: int | None, body: bytes):
    bot = AsyncMock()
    bot.send_chat_action = AsyncMock()
    bot.get_file = AsyncMock(
        return_value=SimpleNamespace(file_path="f.bin", file_size=file_size)
    )
    bot.download_file = AsyncMock(return_value=io.BytesIO(body))
    return bot


def make_user_and_budget():
    user = SimpleNamespace(
        id=uuid.uuid4(),
        family_budget_id=uuid.uuid4(),
        default_wallet_id=uuid.uuid4(),
    )
    budget = FamilyBudget(
        daily_model_calls=0,
        daily_unparsed=0,
        counters_day=tashkent_today_for_counters(),
    )
    budget.id = user.family_budget_id
    budget.is_deleted = False
    wallet = SimpleNamespace(id=user.default_wallet_id, is_deleted=False, currency="UZS")
    return user, budget, wallet


# --------------------------------------------------------------------------
# Task 1a: unregistered sender -> zero downloads.
# --------------------------------------------------------------------------


async def test_unregistered_voice_sender_never_downloads():
    message = make_message(telegram_id=999, voice=True)
    bot = make_bot(file_size=100, body=b"x")

    with patch(
        "bot.quick_entry.handlers.get_active_user_by_telegram_id",
        AsyncMock(return_value=None),
    ):
        await handle_quick_entry_voice(message, bot)

    bot.get_file.assert_not_called()
    bot.download_file.assert_not_called()
    message.answer.assert_awaited_once_with(MESSAGES["not_registered"]["ru"])


async def test_unregistered_photo_sender_never_downloads():
    message = make_message(telegram_id=999, voice=False)
    bot = make_bot(file_size=100, body=b"x")

    with patch(
        "bot.quick_entry.receipt_photo.get_active_user_by_telegram_id",
        AsyncMock(return_value=None),
    ):
        await handle_receipt_photo(message, bot)

    bot.get_file.assert_not_called()
    bot.download_file.assert_not_called()
    message.answer.assert_awaited_once_with(MESSAGES["not_registered"]["ru"])


# --------------------------------------------------------------------------
# Task 1b: oversized files are never downloaded.
# --------------------------------------------------------------------------


async def test_oversized_voice_never_downloaded():
    user, budget, wallet = make_user_and_budget()
    message = make_message(telegram_id=1, voice=True)
    bot = make_bot(file_size=MAX_VOICE_BYTES + 1, body=b"x" * 10)

    session = FakeSession({(FamilyBudget, user.family_budget_id): budget})
    with (
        patch(
            "bot.quick_entry.handlers.get_active_user_by_telegram_id",
            AsyncMock(return_value=user),
        ),
        patch(
            "bot.quick_entry.handlers.async_session_factory",
            FakeSessionFactory(session),
        ),
        patch(
            "bot.quick_entry.handlers._get_default_wallet",
            AsyncMock(return_value=wallet),
        ),
        # Guard against a real network call to the parser if the size
        # check is ever removed/broken and execution falls through.
        patch("bot.quick_entry.handlers.PARSER_PROVIDER", None),
    ):
        await handle_quick_entry_voice(message, bot)

    bot.get_file.assert_awaited_once()
    bot.download_file.assert_not_called()
    message.answer.assert_awaited_once_with(MSG_MODEL_FAIL)


async def test_oversized_photo_never_downloaded():
    user, budget, wallet = make_user_and_budget()
    message = make_message(telegram_id=1, voice=False)
    bot = make_bot(file_size=MAX_PHOTO_BYTES + 1, body=b"x" * 10)

    session = FakeSession({(FamilyBudget, user.family_budget_id): budget})
    with (
        patch(
            "bot.quick_entry.receipt_photo.get_active_user_by_telegram_id",
            AsyncMock(return_value=user),
        ),
        patch(
            "bot.quick_entry.receipt_photo.async_session_factory",
            FakeSessionFactory(session),
        ),
        patch(
            "bot.quick_entry.receipt_photo._get_default_wallet",
            AsyncMock(return_value=wallet),
        ),
        patch("bot.quick_entry.receipt_photo.PARSER_PROVIDER", None),
    ):
        await handle_receipt_photo(message, bot)

    bot.get_file.assert_awaited_once()
    bot.download_file.assert_not_called()
    message.answer.assert_awaited_once_with(MSG_MODEL_FAIL)


# --------------------------------------------------------------------------
# Task 2: amount / rate bounds and comment truncation.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("amount", [0, -5000, 3_000_000_000])
def test_bad_amounts_are_filtered_out_of_every_bucket(amount: int) -> None:
    expense_op = ParsedOperation(
        type="expense",
        amount=amount,
        currency="UZS",
        wallet_hint=None,
        category=None,
        comment=None,
    )
    ambiguous_op = ParsedOperation(
        type="ambiguous",
        amount=amount,
        currency="UZS",
        wallet_hint=None,
        category=None,
        comment=None,
    )
    transfer_op = ParsedOperation(
        type="transfer",
        amount=amount,
        currency="UZS",
        wallet_hint=None,
        category=None,
        comment=None,
    )
    assert _filter_countable([expense_op, ambiguous_op, transfer_op]) == []
    assert _is_clear(expense_op) is False
    assert _is_ambiguous(ambiguous_op) is False
    assert _is_transfer_op(transfer_op) is False


async def test_bad_amount_operation_produces_no_amount_reply_and_no_transaction():
    user, budget, wallet = make_user_and_budget()
    message = make_message(telegram_id=1, voice=True)
    session = FakeSession()

    bad_op = ParsedOperation(
        type="expense",
        amount=-5000,
        currency="UZS",
        wallet_hint=None,
        category=None,
        comment=None,
    )
    response = ParseResponse(operations=[bad_op])

    never_create = AsyncMock(side_effect=AssertionError("must not create a transaction"))
    with (
        patch("bot.quick_entry.handlers.create_quick_entry_expense", never_create),
        patch("bot.quick_entry.handlers.create_quick_entry_income", never_create),
        patch("bot.quick_entry.handlers.create_quick_entry_transfer", never_create),
    ):
        await _process_parsed_response(
            message,
            AsyncMock(),
            session,
            user,
            budget,
            wallet,
            response,
            "",
            date.today(),
        )

    message.answer.assert_awaited_once_with(MSG_NO_AMOUNT)


def test_absurd_transfer_rate_is_rejected() -> None:
    from bot.quick_entry.handlers import _resolve_rate
    from app.services.quick_entry_transfer import effective_rate

    op = ParsedOperation(
        type="transfer",
        amount=1000,
        currency="UZS",
        wallet_hint=None,
        category=None,
        comment=None,
        rate=9_000_000_000,
    )
    assert _resolve_rate(op, "") is None
    assert effective_rate(op, "по курсу") is None


def test_comment_is_truncated_to_200_chars() -> None:
    long_comment = "a" * 500
    op = ParsedOperation(
        type="expense",
        amount=1000,
        currency="UZS",
        wallet_hint=None,
        category=None,
        comment=long_comment,
    )
    result = _strip_op_comment(op, "")
    assert result is not None
    assert len(result) == 200


# --------------------------------------------------------------------------
# Task 3: concurrent counter increments must not lose an update.
#
# Driven through the real `spend_model_call`/`ensure_counters_day` code
# path against a real (sqlite, via aiosqlite) database — not a mock — so
# the atomic UPDATE really executes at the DB layer.
# --------------------------------------------------------------------------


async def test_concurrent_spend_model_call_does_not_lose_increments():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp.name}")
        async with engine.begin() as conn:
            await conn.run_sync(
                Base.metadata.create_all, tables=[FamilyBudget.__table__]
            )

        async with AsyncSession(engine, expire_on_commit=False) as setup_session:
            budget = FamilyBudget(
                daily_model_calls=0,
                daily_unparsed=0,
                counters_day=tashkent_today_for_counters(),
            )
            setup_session.add(budget)
            await setup_session.commit()
            await setup_session.refresh(budget)
            budget_id = budget.id

        concurrency = 20

        async def _one_increment() -> None:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                local_budget = await session.get(FamilyBudget, budget_id)
                await spend_model_call(session, local_budget)
                await session.commit()

        await asyncio.gather(*[_one_increment() for _ in range(concurrency)])

        async with AsyncSession(engine, expire_on_commit=False) as check_session:
            final = await check_session.get(FamilyBudget, budget_id)
            assert final.daily_model_calls == concurrency

        await engine.dispose()


# --------------------------------------------------------------------------
# Task 4: Markdown injection via user-controlled values.
# --------------------------------------------------------------------------


def test_wallet_name_markdown_metacharacters_are_escaped() -> None:
    card = format_card(
        sign="➖",
        amount=1000,
        currency="UZS",
        category_label="Такси",
        comment=None,
        wallet_name="Карта*[x](tg://user?id=1)",
        op_date=date(2026, 1, 1),
        balance=0,
    )
    assert "Карта\\*\\[x\\](tg://user?id=1)" in card
    # unescaped forms must not survive into the message body
    assert "Карта*[x]" not in card


def test_escape_markdown_helper_escapes_all_special_chars() -> None:
    assert escape_markdown("a*b_c`d[e]f") == "a\\*b\\_c\\`d\\[e\\]f"
