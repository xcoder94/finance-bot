"""m3-4a: a message without an amount adds items to the family shopping list.

Updates go through a real aiogram Dispatcher/Message/Bot into the real handlers
on a real Postgres. Only the AI parser is replaced, at its outer boundary
(set_parser_override); routing and the shopping service are the real code.
"""

from __future__ import annotations

import io
import json
import time
import uuid
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from aiogram import Bot, Dispatcher
from aiogram.methods import SendMessage
from aiogram.types import File, Update
from sqlalchemy import func, select

from app.models.shopping import ShoppingItem
from app.models.family_budget import FamilyBudget
from app.models.transaction import Transaction
from app.parsing.http_adapter import HttpParser
from app.parsing.prompt import IMMUTABLE_PARSER_INSTRUCTIONS
from app.parsing.stub import StubParser
from app.parsing.types import ParseRequest, ParseResponse, ParsedOperation, ParserMalformed
from bot.quick_entry.handlers import router as quick_entry_router
from bot.quick_entry.handlers import set_parser_override
from bot.quick_entry.texts import MSG_NO_AMOUNT
from tests.test_quick_entry_flow import (
    SessionFactory,
    create_user,
    make_wallet,
    pytestmark,  # noqa: F401  (anyio + db skip marks)
    rollback_session,
    seed_taxi_setup,
)

MAX_ITEMS_PER_MESSAGE = 20


class FakeBot(Bot):
    """Real Bot object; the network call is replaced by a recorder."""

    def __init__(self) -> None:
        super().__init__(token="123456:TESTTOKEN")
        self.sent: list[SendMessage] = []

    async def __call__(self, method: Any, request_timeout: Any = None) -> Any:
        if isinstance(method, SendMessage):
            self.sent.append(method)
            return None
        if method.__api_method__ == "getFile":
            return File(file_id="f", file_unique_id="u", file_size=5, file_path="v.oga")
        return True

    async def download_file(self, *_a: Any, **_k: Any) -> io.BytesIO:  # type: ignore[override]
        return io.BytesIO(b"ogg")


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


async def feed(bot: FakeBot, update: Update) -> None:
    dp = Dispatcher()
    dp.include_router(quick_entry_router)
    try:
        await dp.feed_update(bot, update)
    finally:
        quick_entry_router._parent_router = None


async def send_text(session, monkeypatch, user, text: str, parser) -> FakeBot:
    set_parser_override(parser)
    monkeypatch.setattr("bot.quick_entry.handlers.async_session_factory", SessionFactory(session))
    bot = FakeBot()
    await feed(bot, _update(user.telegram_id, text=text))
    return bot


async def send_voice(session, monkeypatch, user, parser) -> FakeBot:
    set_parser_override(parser)
    monkeypatch.setattr("bot.quick_entry.handlers.async_session_factory", SessionFactory(session))
    monkeypatch.setattr("bot.quick_entry.handlers.PARSER_PROVIDER", "google")
    monkeypatch.setattr("bot.quick_entry.handlers.PARSER_API_KEY", "test-not-real")
    bot = FakeBot()
    await feed(
        bot,
        _update(user.telegram_id, voice={"file_id": "f", "file_unique_id": "u", "duration": 1}),
    )
    return bot


def items_response(*names: str, speech: str | None = None) -> ParseResponse:
    return ParseResponse(operations=[], shopping_items=list(names), speech_status=speech)


async def family_items(session, budget) -> list[str]:
    rows = await session.scalars(
        select(ShoppingItem.name)
        .where(ShoppingItem.family_budget_id == budget.id)
        .order_by(ShoppingItem.created_at)
    )
    return list(rows)


@pytest.fixture(autouse=True)
def _reset() -> Any:
    set_parser_override(None)
    yield
    set_parser_override(None)


class TestText:
    async def test_three_items_go_to_family_list(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_340_001)
            await seed_taxi_setup(session, user, budget)
            other_user, other_budget = await create_user(session, telegram_id=9_340_002)
            parser = StubParser(
                responses={"молоко, хлеб, яйца": items_response("молоко", "хлеб", "яйца")}
            )
            monkeypatch.setattr("bot.onboarding.MINI_APP_URL", "https://app.example/")

            bot = await send_text(session, monkeypatch, user, "молоко, хлеб, яйца", parser)

            assert await family_items(session, budget) == ["молоко", "хлеб", "яйца"]
            assert await family_items(session, other_budget) == []
            assert len(bot.sent) == 1
            sent = bot.sent[0]
            assert sent.text == "Добавил в список покупок: молоко, хлеб, яйца."
            assert sent.parse_mode == "Markdown"
            assert sent.reply_markup.inline_keyboard[0][0].web_app.url == "https://app.example/"
            assert await session.scalar(select(func.count()).select_from(Transaction)) == 0
            await session.refresh(budget)
            assert budget.daily_model_calls == 1  # one of 50

    async def test_message_reaches_the_parser_not_no_amount(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_340_003)
            await seed_taxi_setup(session, user, budget)
            seen: list[ParseRequest] = []

            class Recorder:
                async def parse(self, request: ParseRequest) -> ParseResponse:
                    seen.append(request)
                    return items_response("молоко")

            bot = await send_text(session, monkeypatch, user, "молоко", Recorder())
            assert [r.text for r in seen] == ["молоко"]
            assert bot.sent[0].text != MSG_NO_AMOUNT

    async def test_expense_with_amount_is_still_a_card(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_340_004)
            await seed_taxi_setup(session, user, budget)
            parser = StubParser()  # default "такси 25 тысяч" is an expense

            bot = await send_text(session, monkeypatch, user, "такси 25 тысяч", parser)

            assert "25 000 сум" in bot.sent[0].text
            assert await family_items(session, budget) == []
            assert await session.scalar(select(func.count()).select_from(Transaction)) == 1

    async def test_amount_message_with_stray_items_stays_expense(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_340_005)
            await seed_taxi_setup(session, user, budget)
            expense = ParsedOperation(
                type="expense", amount=5000, currency="UZS", wallet_hint=None,
                category="Такси", comment=None,
            )
            parser = StubParser(
                responses={
                    "хлеб 5000 сум": ParseResponse(operations=[expense], shopping_items=["хлеб"])
                }
            )
            bot = await send_text(session, monkeypatch, user, "хлеб 5000 сум", parser)
            assert "5 000 сум" in bot.sent[0].text
            assert await family_items(session, budget) == []

    async def test_duplicates_reported_not_added_twice(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_340_006)
            await seed_taxi_setup(session, user, budget)
            session.add(ShoppingItem(family_budget_id=budget.id, name="Хлеб",
                                     added_by_user_id=user.id))
            await session.flush()
            parser = StubParser(responses={"молоко, хлеб": items_response("молоко", "хлеб")})

            bot = await send_text(session, monkeypatch, user, "молоко, хлеб", parser)

            assert sorted(await family_items(session, budget)) == ["Хлеб", "молоко"]
            assert bot.sent[0].text == (
                "Добавил в список покупок: молоко.\nУже были в списке: Хлеб."
            )

    async def test_only_duplicates(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_340_007)
            await seed_taxi_setup(session, user, budget)
            session.add(ShoppingItem(family_budget_id=budget.id, name="хлеб",
                                     added_by_user_id=user.id))
            await session.flush()
            parser = StubParser(responses={"хлеб": items_response("хлеб")})
            bot = await send_text(session, monkeypatch, user, "хлеб", parser)
            assert bot.sent[0].text == "Уже были в списке: хлеб."
            assert await family_items(session, budget) == ["хлеб"]

    async def test_limit_100_partial_add(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_340_008)
            await seed_taxi_setup(session, user, budget)
            session.add_all(
                ShoppingItem(family_budget_id=budget.id, name=f"item{i}",
                             added_by_user_id=user.id)
                for i in range(99)
            )
            await session.flush()
            parser = StubParser(responses={"a, b, c": items_response("a", "b", "c")})

            bot = await send_text(session, monkeypatch, user, "a, b, c", parser)

            assert len(await family_items(session, budget)) == 100
            assert bot.sent[0].text == (
                "Добавил в список покупок: a.\n"
                "В списке уже 100 позиций — остальное не добавил."
            )

    async def test_limit_100_full_list(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_340_009)
            await seed_taxi_setup(session, user, budget)
            session.add_all(
                ShoppingItem(family_budget_id=budget.id, name=f"item{i}",
                             added_by_user_id=user.id)
                for i in range(100)
            )
            await session.flush()
            parser = StubParser(responses={"a, b": items_response("a", "b")})
            bot = await send_text(session, monkeypatch, user, "a, b", parser)
            assert len(await family_items(session, budget)) == 100
            assert bot.sent[0].text == "В списке уже 100 позиций — остальное не добавил."

    async def test_markdown_in_names_is_escaped(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_340_010)
            await seed_taxi_setup(session, user, budget)
            parser = StubParser(responses={"x": items_response("a*b_c[d`e]")})
            bot = await send_text(session, monkeypatch, user, "x", parser)
            assert await family_items(session, budget) == ["a*b_c[d`e]"]  # stored raw
            assert bot.sent[0].text == (
                "Добавил в список покупок: a\\*b\\_c\\[d\\`e\\]."
            )

    async def test_at_most_20_items_per_message(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_340_011)
            await seed_taxi_setup(session, user, budget)
            names = [f"т{i}" for i in range(25)]
            parser = StubParser(responses={"много": items_response(*names)})
            await send_text(session, monkeypatch, user, "много", parser)
            assert await family_items(session, budget) == names[:MAX_ITEMS_PER_MESSAGE]

    async def test_uzbek_user_gets_uzbek_text(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_340_012)
            await seed_taxi_setup(session, user, budget)
            user.language = "uz"
            await session.flush()
            parser = StubParser(responses={"sut, non": items_response("sut", "non")})
            bot = await send_text(session, monkeypatch, user, "sut, non", parser)
            assert bot.sent[0].text == "Xarid ro'yxatiga qo'shdim: sut, non."

    async def test_user_without_wallet_can_still_add_items(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_340_013)
            parser = StubParser(responses={"сыр": items_response("сыр")})
            bot = await send_text(session, monkeypatch, user, "сыр", parser)
            assert await family_items(session, budget) == ["сыр"]
            assert bot.sent[0].text == "Добавил в список покупок: сыр."

    async def test_blank_names_only_is_not_parsed(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_340_014)
            await seed_taxi_setup(session, user, budget)
            parser = StubParser(responses={"?": items_response("  ", "")})
            bot = await send_text(session, monkeypatch, user, "?", parser)
            assert bot.sent[0].text == MSG_NO_AMOUNT
            assert await family_items(session, budget) == []


class TestVoice:
    async def test_voice_list_adds_items(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_340_020)
            await seed_taxi_setup(session, user, budget)
            parser = StubParser(
                audio_responses={"__audio__": items_response("молоко", "хлеб", speech="recognized")}
            )
            bot = await send_voice(session, monkeypatch, user, parser)
            assert await family_items(session, budget) == ["молоко", "хлеб"]
            assert bot.sent[0].text == "Добавил в список покупок: молоко, хлеб."
            await session.refresh(budget)
            assert budget.daily_model_calls == 1

    async def test_voice_limit_and_duplicates(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_340_021)
            await seed_taxi_setup(session, user, budget)
            session.add_all(
                ShoppingItem(family_budget_id=budget.id, name=f"item{i}",
                             added_by_user_id=user.id)
                for i in range(99)
            )
            session.add(ShoppingItem(family_budget_id=budget.id, name="Хлеб",
                                     added_by_user_id=user.id))
            await session.flush()
            parser = StubParser(
                audio_responses={
                    "__audio__": items_response("хлеб", "молоко", "яйца", speech="recognized")
                }
            )
            bot = await send_voice(session, monkeypatch, user, parser)
            assert len(await family_items(session, budget)) == 100
            assert bot.sent[0].text == (
                "Уже были в списке: Хлеб.\n"
                "В списке уже 100 позиций — остальное не добавил."
            )

    async def test_voice_not_recognized_unchanged(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget = await create_user(session, telegram_id=9_340_022)
            await seed_taxi_setup(session, user, budget)
            parser = StubParser(
                audio_responses={"__audio__": ParseResponse(operations=[], speech_status="not_recognized")}
            )
            bot = await send_voice(session, monkeypatch, user, parser)
            assert "Не разобрал голосовое" in bot.sent[0].text
            assert await family_items(session, budget) == []


class TestParserContract:
    def test_prompt_documents_shopping_items_and_stays_static(self) -> None:
        assert "shopping_items" in IMMUTABLE_PARSER_INSTRUCTIONS
        assert "cache" not in IMMUTABLE_PARSER_INSTRUCTIONS.lower()

    async def _parse(self, payload: dict) -> ParseResponse:
        def handler(_req: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, json={"choices": [{"message": {"content": json.dumps(payload)}}]}
            )

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        parser = HttpParser("openai", "k", "m", client=client)
        return await parser.parse(
            ParseRequest(text="молоко", wallet_names=[], expense_category_names=[],
                         income_category_names=[])
        )

    async def test_http_parser_reads_shopping_items(self) -> None:
        r = await self._parse({"operations": [], "shopping_items": ["молоко", "хлеб"]})
        assert r.shopping_items == ["молоко", "хлеб"]

    async def test_http_parser_missing_field_means_empty(self) -> None:
        r = await self._parse({"operations": []})
        assert r.shopping_items == []

    @pytest.mark.parametrize("bad", ["молоко", [1, 2], {"a": 1}])
    async def test_http_parser_rejects_malformed_items(self, bad) -> None:
        with pytest.raises(ParserMalformed):
            await self._parse({"operations": [], "shopping_items": bad})
