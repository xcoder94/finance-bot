"""ux-fix-backend: B3 sibling-unique colours, B15 too-large amount, B16 help/menu, B20 /start."""

from __future__ import annotations

import time
import uuid
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from aiogram import Dispatcher
from aiogram.methods import SendMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense_category import ExpenseCategory
from app.models.income_category import IncomeCategory
from app.parsing.stub import StubParser
from app.parsing.types import ParseResponse, ParsedOperation
from app.services.bot_texts import CATALOGUE, t
from app.services.budget_seed import copy_seed_categories_only
from bot.onboarding import router as onboarding_router
from bot.phone_prompt import router as phone_router
from bot.quick_entry.handlers import (
    handle_quick_entry_text,
    set_parser_override,
)
from bot.quick_entry.handlers import router as quick_entry_router
from tests.test_m3_4_bot_shopping import FakeBot, _update
from tests.test_quick_entry_flow import (
    SessionFactory,
    create_user,
    pytestmark,  # noqa: F401
    rollback_session,
    seed_taxi_setup,
)
from tests.test_wallets_categories import (
    api_client,
    auth_headers,
    create_user_with_budget,
)

__all__ = ["api_client"]


@pytest.fixture(autouse=True)
def _reset_parser():
    set_parser_override(None)
    yield
    set_parser_override(None)


# ---------------------------------------------------------------- B3 colours


async def _expense_rows(session: AsyncSession, budget_id: uuid.UUID):
    return list(
        await session.scalars(
            select(ExpenseCategory).where(ExpenseCategory.family_budget_id == budget_id)
        )
    )


async def test_seed_colours_unique_per_level() -> None:
    async with rollback_session() as session:
        _, budget = await create_user(session, telegram_id=9_610_001)
        await copy_seed_categories_only(session, budget.id)
        await session.flush()
        rows = await _expense_rows(session, budget.id)
        parents = [r for r in rows if r.parent_id is None]
        assert len(parents) == 7
        assert len({r.color_index for r in parents}) == 7
        for p in parents:
            subs = [r.color_index for r in rows if r.parent_id == p.id]
            assert len(subs) == len(set(subs)), p.name
        income = list(
            await session.scalars(
                select(IncomeCategory.color_index).where(
                    IncomeCategory.family_budget_id == budget.id
                )
            )
        )
        assert len(income) == len(set(income))


async def test_eighth_parent_gets_unused_index(api_client) -> None:
    client, session = api_client
    tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    _, budget = await create_user_with_budget(session, telegram_id=tid)
    for idx in (1, 2, 3, 4, 5, 6, 8):
        session.add(
            ExpenseCategory(
                family_budget_id=budget.id, name=f"P{idx}", color_index=idx
            )
        )
    await session.flush()
    resp = await client.post(
        "/api/v1/categories/expense",
        headers=auth_headers(tid),
        json={"name": "Eighth"},
    )
    assert resp.status_code == 201
    assert resp.json()["color_index"] == 7


async def test_subcategory_colour_unique_among_siblings_only(api_client) -> None:
    client, session = api_client
    tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    _, budget = await create_user_with_budget(session, telegram_id=tid)
    # parents occupy 1..3; they must not influence subcategory choice
    parents = []
    for idx in (1, 2, 3):
        p = ExpenseCategory(
            family_budget_id=budget.id, name=f"P{idx}", color_index=idx
        )
        session.add(p)
        parents.append(p)
    await session.flush()
    session.add(
        ExpenseCategory(
            family_budget_id=budget.id,
            name="S1",
            parent_id=parents[0].id,
            color_index=1,
        )
    )
    await session.flush()
    headers = auth_headers(tid)
    r1 = await client.post(
        "/api/v1/categories/expense",
        headers=headers,
        json={"name": "S2", "parent_id": str(parents[0].id)},
    )
    assert r1.json()["color_index"] == 2
    r2 = await client.post(
        "/api/v1/categories/expense",
        headers=headers,
        json={"name": "Other first", "parent_id": str(parents[1].id)},
    )
    assert r2.json()["color_index"] == 1


async def test_all_eight_used_cycles_by_sibling_count(api_client) -> None:
    client, session = api_client
    tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    _, budget = await create_user_with_budget(session, telegram_id=tid)
    parent = ExpenseCategory(family_budget_id=budget.id, name="P", color_index=1)
    session.add(parent)
    await session.flush()
    for idx in range(1, 8):
        session.add(
            ExpenseCategory(
                family_budget_id=budget.id,
                name=f"S{idx}",
                parent_id=parent.id,
                color_index=idx,
            )
        )
    await session.flush()
    # 7 subs with 1..7; the 8th takes the free 8
    r8 = await client.post(
        "/api/v1/categories/expense",
        headers=auth_headers(tid),
        json={"name": "S8", "parent_id": str(parent.id)},
    )
    assert r8.status_code == 201
    assert r8.json()["color_index"] == 8


async def test_income_colour_unique_among_income_only(api_client) -> None:
    client, session = api_client
    tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    _, budget = await create_user_with_budget(session, telegram_id=tid)
    session.add(
        ExpenseCategory(family_budget_id=budget.id, name="E", color_index=1)
    )
    await session.flush()
    resp = await client.post(
        "/api/v1/categories/income",
        headers=auth_headers(tid),
        json={"name": "Salary"},
    )
    assert resp.json()["color_index"] == 1


async def test_existing_colours_not_rewritten(api_client) -> None:
    client, session = api_client
    tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    _, budget = await create_user_with_budget(session, telegram_id=tid)
    old = []
    for i in range(3):  # old collision: three parents all colour 2
        c = ExpenseCategory(family_budget_id=budget.id, name=f"Old{i}", color_index=2)
        session.add(c)
        old.append(c)
    await session.flush()
    resp = await client.post(
        "/api/v1/categories/expense",
        headers=auth_headers(tid),
        json={"name": "New"},
    )
    assert resp.status_code == 201
    assert resp.json()["color_index"] == 1
    for c in old:
        await session.refresh(c)
        assert c.color_index == 2


# ------------------------------------------------------- B15 too large amount


class _FixedParser:
    def __init__(self, amount: int) -> None:
        self.amount = amount

    async def parse(self, request: Any) -> ParseResponse:
        return ParseResponse(
            operations=[
                ParsedOperation(
                    type="expense", amount=self.amount, currency="UZS", category="Такси"
                )
            ]
        )


def _message(telegram_id: int, text: str) -> SimpleNamespace:
    return SimpleNamespace(
        from_user=SimpleNamespace(id=telegram_id), text=text, answer=AsyncMock()
    )


EXPECTED_TOO_LARGE_RU = (
    "Слишком большая сумма — больше 2 000 000 000 сум записать нельзя. Проверьте число."
)


async def test_amount_over_max_has_own_message_and_keeps_counter(monkeypatch) -> None:
    async with rollback_session() as session:
        user, budget = await create_user(session, telegram_id=9_610_020)
        await seed_taxi_setup(session, user, budget)
        monkeypatch.setattr(
            "bot.quick_entry.handlers.async_session_factory", SessionFactory(session)
        )
        set_parser_override(_FixedParser(3_000_000_000))
        msg = _message(user.telegram_id, "такси 3000000000")
        await handle_quick_entry_text(msg, SimpleNamespace())
        msg.answer.assert_awaited_once_with(EXPECTED_TOO_LARGE_RU)
        await session.refresh(budget)
        assert budget.daily_unparsed == 0


def test_too_large_text_uz_and_ru_catalogue() -> None:
    assert t("ru", "quick.amount_too_large", max="2 000 000 000") == EXPECTED_TOO_LARGE_RU
    assert "2 000 000 000" in t("uz", "quick.amount_too_large", max="2 000 000 000")


# ------------------------------------------------------- B16 help / menu / B20


async def _feed_all(bot, update) -> None:
    from bot.help import router as help_router

    dp = Dispatcher()
    routers = (phone_router, onboarding_router, quick_entry_router, help_router)
    for r in routers:
        dp.include_router(r)
    try:
        await dp.feed_update(bot, update)
    finally:
        for r in routers:
            r._parent_router = None


def _cmd(command: str) -> dict[str, Any]:
    return {
        "text": command,
        "entities": [{"type": "bot_command", "offset": 0, "length": len(command.split()[0])}],
    }


HELP_RU = (
    "Напишите трату или доход обычным текстом, например: такси 25 тысяч. "
    "Или откройте приложение."
)


def _has_open_app_button(sent: SendMessage) -> bool:
    markup = sent.reply_markup
    if markup is None:
        return False
    return any(b.web_app is not None for row in markup.inline_keyboard for b in row)


@pytest.mark.parametrize("command", ["/help", "/menu", "/foo", "/foo bar"])
async def test_help_menu_unknown_command_reply(monkeypatch, command) -> None:
    monkeypatch.setattr("bot.onboarding.MINI_APP_URL", "https://app.example")
    async with rollback_session() as session:
        user, _ = await create_user(session, telegram_id=9_610_030)
        for target in (
            "bot.onboarding.async_session_factory",
            "bot.help.async_session_factory",
            "bot.phone_prompt.async_session_factory",
            "bot.quick_entry.handlers.async_session_factory",
        ):
            monkeypatch.setattr(target, SessionFactory(session))
        bot = FakeBot()
        await _feed_all(bot, _update(user.telegram_id, **_cmd(command)))
        assert [m.text for m in bot.sent] == [HELP_RU]
        assert _has_open_app_button(bot.sent[0])


async def test_help_in_uzbek_for_uz_user(monkeypatch) -> None:
    monkeypatch.setattr("bot.onboarding.MINI_APP_URL", "https://app.example")
    async with rollback_session() as session:
        user, _ = await create_user(session, telegram_id=9_610_031)
        user.language = "uz"
        await session.flush()
        for target in (
            "bot.onboarding.async_session_factory",
            "bot.help.async_session_factory",
            "bot.phone_prompt.async_session_factory",
            "bot.quick_entry.handlers.async_session_factory",
        ):
            monkeypatch.setattr(target, SessionFactory(session))
        bot = FakeBot()
        await _feed_all(bot, _update(user.telegram_id, **_cmd("/help")))
        assert bot.sent[0].text == t("uz", "help.hint")
        assert bot.sent[0].text != HELP_RU


async def test_registered_start_names_budget_with_button(monkeypatch) -> None:
    monkeypatch.setattr("bot.onboarding.MINI_APP_URL", "https://app.example")
    async with rollback_session() as session:
        user, budget = await create_user(session, telegram_id=9_610_032)
        budget.name = "Семья Юсуповых"
        await session.flush()
        for target in (
            "bot.onboarding.async_session_factory",
            "bot.help.async_session_factory",
            "bot.phone_prompt.async_session_factory",
        ):
            monkeypatch.setattr(target, SessionFactory(session))
        bot = FakeBot()
        await _feed_all(bot, _update(user.telegram_id, **_cmd("/start")))
        assert [m.text for m in bot.sent] == ["Вы уже в семейном бюджете «Семья Юсуповых»."]
        assert _has_open_app_button(bot.sent[0])


async def test_command_menu_registered_for_ru_and_uz() -> None:
    from bot.help import register_bot_commands

    bot = AsyncMock()
    await register_bot_commands(bot)
    calls = bot.set_my_commands.await_args_list
    assert len(calls) == 2
    by_lang = {c.kwargs.get("language_code"): c for c in calls}
    assert set(by_lang) == {None, "uz"}
    for call in calls:
        cmds = call.args[0]
        assert [c.command for c in cmds] == ["start", "help"]
    assert by_lang["uz"].args[0][1].description == t("uz", "command.help")


def test_no_family_budget_string_in_bot_texts() -> None:
    for entry in CATALOGUE.values():
        for text in entry.values():
            assert "Family Budget" not in text


# ------------------------------------------- r2 #5: partial save + notice


class _TwoOpsParser:
    def __init__(self, big_first: bool) -> None:
        self.big_first = big_first

    async def parse(self, request: Any) -> ParseResponse:
        big = ParsedOperation(
            type="expense", amount=3_000_000_000, currency="UZS",
            wallet_hint=None, category="Такси", comment="такси",
        )
        ok = ParsedOperation(
            type="expense", amount=5000, currency="UZS",
            wallet_hint=None, category="Такси", comment="хлеб",
        )
        return ParseResponse(operations=[big, ok] if self.big_first else [ok, big])


@pytest.mark.parametrize("big_first", [True, False])
@pytest.mark.parametrize("lang", ["ru", "uz"])
async def test_over_max_op_reported_next_to_saved_op(monkeypatch, big_first, lang) -> None:
    async with rollback_session() as session:
        user, budget = await create_user(
            session, telegram_id=9_610_030 + (1 if big_first else 0) + (2 if lang == "uz" else 0)
        )
        user.language = lang
        await seed_taxi_setup(session, user, budget)
        monkeypatch.setattr(
            "bot.quick_entry.handlers.async_session_factory", SessionFactory(session)
        )
        set_parser_override(_TwoOpsParser(big_first))
        msg = _message(user.telegram_id, "такси 3000000000 хлеб 5000")
        await handle_quick_entry_text(msg, SimpleNamespace())
        texts = [c.args[0] for c in msg.answer.await_args_list]
        assert len(texts) == 2
        notice = [x for x in texts if "3 000 000 000" in x]
        assert len(notice) == 1
        assert "2 000 000 000" in notice[0]
        assert "такси" in notice[0].lower() or "taksi" in notice[0].lower()
        card = [x for x in texts if x is not notice[0]][0]
        assert "5 000" in card
