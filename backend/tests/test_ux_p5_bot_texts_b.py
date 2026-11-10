"""ux-p5-backend-b: quick-entry card, buttons, errors, reminders, digest, goal texts in the
user's language; category names by translation_key; Uzbek cascade keywords."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.models.expense_category import ExpenseCategory
from app.models.goal import Goal
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.parsing.cascade_keywords import CASCADE_KEYWORDS
from app.parsing.prefilter import PrefilterCategory, try_prefilter
from app.parsing.types import ParseResponse, ParsedOperation
from app.services.bot_texts import CATALOGUE, t
from app.services.budget_seed import (
    LEGACY_SEED_EXPENSE_CATEGORIES as SEED_EXPENSE_CATEGORIES,  # keyword keys of old budgets
    LEGACY_SEED_INCOME_CATEGORIES as SEED_INCOME_CATEGORIES,
    SEED_WALLETS,
    copy_seed_categories_only,
)
from app.services.display_name import (
    SEED_NAMES_UZ,
    build_seed_name_by_key,
    display_name,
)
from app.services.evening_reminder import send_evening_reminders_for_family
from app.services.goal_notify import fan_out_achievement, format_achievement_message
from app.services.release_announcement import release_announcement_text
from app.services.weekly_digest import build_digest_body, send_weekly_digest_for_family
from bot.quick_entry.cards import (
    card_keyboard,
    format_amount,
    format_card,
    format_exchange_card,
    format_transfer_card,
    transfer_card_keyboard,
    type_question_keyboard,
)
from bot.quick_entry.handlers import handle_quick_entry_text, set_parser_override
from bot.quick_entry.texts import (
    MSG_NO_AMOUNT,
    currency_missing_text,
    model_limit_text,
    unparsed_limit_text,
)
from tests.test_quick_entry_flow import (
    SessionFactory,
    create_user,
    make_wallet,
    pytestmark,  # noqa: F401
    rollback_session,
)
from tests.test_wallets_categories import api_client, create_user_with_budget  # noqa: F401

TASHKENT = ZoneInfo("Asia/Tashkent")
LOCALES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "i18n" / "locales"


@pytest.fixture(autouse=True)
def _reset_parser():
    set_parser_override(None)
    yield
    set_parser_override(None)


class _TaxiParser:
    async def parse(self, request):
        return ParseResponse(
            operations=[
                ParsedOperation(
                    type="expense", amount=25_000, currency="UZS", category="Такси",
                    wallet_hint=None, comment=None,
                )
            ]
        )


def _msg(telegram_id: int, text: str) -> SimpleNamespace:
    return SimpleNamespace(
        from_user=SimpleNamespace(id=telegram_id), text=text, answer=AsyncMock()
    )


def _buttons(markup) -> list[str]:
    return [b.text for row in markup.inline_keyboard for b in row]


async def _seeded_user(session, tid: int, language: str):
    user, budget = await create_user(session, telegram_id=tid)
    user.language = language
    await copy_seed_categories_only(session, budget.id, legacy=True)
    wallet = make_wallet(budget, name="Наличный сум")
    wallet.translation_key = "cash_uzs"
    session.add(wallet)
    await session.flush()
    user.default_wallet_id = wallet.id
    await session.flush()
    return user, budget, wallet


# ------------------------------------------------------- category display names


def test_display_name_uz_default_renamed_and_unknown() -> None:
    assert display_name("Такси", "taxi", language="uz") == "Taksi"
    assert display_name("Taksi", "taxi", language="uz") == "Taksi"
    assert display_name("Мой таксист", "taxi", language="uz") == "Мой таксист"
    assert display_name("Такси", "taxi", language="ru") == "Такси"
    assert display_name("Такси", "taxi") == "Такси"
    assert display_name("Свой", None, language="uz") == "Свой"
    assert display_name("Что-то", "no_such_key", language="uz") == "Что-то"
    assert display_name("Наличный сум", "cash_uzs", language="uz") == "Naqd so'm"


def test_seed_names_uz_cover_every_seed_key_and_match_app_locale() -> None:
    assert set(build_seed_name_by_key()) <= set(SEED_NAMES_UZ)
    uz_json = LOCALES / "uz.json"
    if not uz_json.exists():
        pytest.skip("frontend locales not available")
    app_uz = json.loads(uz_json.read_text(encoding="utf-8"))["defaultEntities"]
    for key, value in SEED_NAMES_UZ.items():
        # keys of the U7 set are not in the app's uz.json until the frontend adds them
        if key in app_uz:
            assert app_uz[key] == value, key
    for value in SEED_NAMES_UZ.values():
        assert "’" not in value and "ʻ" not in value


# ------------------------------------------------------------ the quick-entry card


async def test_acceptance_taksi_card_is_uzbek(monkeypatch) -> None:
    """PRD-ux U6 item 2: card, buttons and category name are Uzbek."""
    async with rollback_session() as session:
        user, _, _ = await _seeded_user(session, 9_620_001, "uz")
        monkeypatch.setattr(
            "bot.quick_entry.handlers.async_session_factory", SessionFactory(session)
        )
        set_parser_override(_TaxiParser())
        msg = _msg(user.telegram_id, "taksi 25 ming")
        await handle_quick_entry_text(msg, SimpleNamespace())
        msg.answer.assert_awaited_once()
        text = msg.answer.await_args.args[0]
        today = datetime.now(TASHKENT).date()
        month = t("uz", f"month.{today.month}")
        assert text.splitlines() == [
            "➖ **25 000 so'm** · Taksi",
            f"Naqd so'm · {today.day} {month}",
            "Qoldiq: -25 000 so'm",
        ]
        assert _buttons(msg.answer.await_args.kwargs["reply_markup"]) == [
            "Hamyon",
            "Tahrirlash",
            "O'chirish",
        ]
        assert "Такси" not in text and "Осталось" not in text


async def test_ru_user_card_unchanged(monkeypatch) -> None:
    async with rollback_session() as session:
        user, _, _ = await _seeded_user(session, 9_620_002, "ru")
        monkeypatch.setattr(
            "bot.quick_entry.handlers.async_session_factory", SessionFactory(session)
        )
        set_parser_override(_TaxiParser())
        msg = _msg(user.telegram_id, "такси 25 тысяч")
        await handle_quick_entry_text(msg, SimpleNamespace())
        text = msg.answer.await_args.args[0]
        today = datetime.now(TASHKENT).date()
        assert text.splitlines()[0] == "➖ **25 000 сум** · Такси"
        assert text.splitlines()[2] == "Осталось: -25 000 сум"
        assert text.splitlines()[1].startswith("Наличный сум · ")
        assert _buttons(msg.answer.await_args.kwargs["reply_markup"]) == [
            "Кошелёк",
            "Изменить",
            "Удалить",
        ]
        assert today.day  # date text itself is pinned by test_quick_entry_cards


async def test_uz_card_renamed_category_shows_users_own_name(monkeypatch) -> None:
    async with rollback_session() as session:
        user, budget, _ = await _seeded_user(session, 9_620_003, "uz")
        taxi = await session.scalar(
            select(ExpenseCategory).where(
                ExpenseCategory.family_budget_id == budget.id,
                ExpenseCategory.translation_key == "taxi",
            )
        )
        taxi.name = "Такси работа"
        await session.flush()
        monkeypatch.setattr(
            "bot.quick_entry.handlers.async_session_factory", SessionFactory(session)
        )

        class _P:
            async def parse(self, request):
                return ParseResponse(
                    operations=[
                        ParsedOperation(
                            type="expense", amount=5_000, currency="UZS",
                            category="Такси работа", wallet_hint=None, comment=None,
                        )
                    ]
                )

        set_parser_override(_P())
        msg = _msg(user.telegram_id, "taksi 5 ming")
        await handle_quick_entry_text(msg, SimpleNamespace())
        assert "· Такси работа" in msg.answer.await_args.args[0]


async def test_uz_card_without_category_label(monkeypatch) -> None:
    text = format_card(
        sign="➖", amount=1000, currency="UZS", category_label=None, comment=None,
        wallet_name="X", op_date=date(2026, 3, 5), balance=5, language="uz",
    )
    assert text.splitlines()[0] == "➖ **1 000 so'm** · Toifasiz"
    assert text.splitlines()[1] == "X · 5 mart"


def test_format_amount_languages() -> None:
    assert format_amount(25000, "UZS") == "25 000 сум"
    assert format_amount(25000, "UZS", "uz") == "25 000 so'm"
    assert format_amount(25000, "USD", "uz") == "25 000 $"


def test_uz_transfer_and_exchange_cards() -> None:
    tr = format_transfer_card(
        amount=1000, currency="UZS", from_wallet_name="A", to_wallet_name="B",
        op_date=date(2026, 1, 2), from_balance=1, to_balance=2, language="uz",
    )
    assert tr.splitlines()[0] == "↔️ **1 000 so'm** · O'tkazma"
    assert tr.splitlines()[1] == "A → B · 2 yanvar"
    ex = format_exchange_card(
        amount=1000, from_currency="UZS", to_amount=1, to_currency="USD", rate=12800,
        op_date=date(2026, 1, 2), from_wallet_name="A", to_wallet_name="B",
        from_balance=1, to_balance=2, language="uz",
    )
    assert ex.splitlines()[0] == "🔄 **1 000 so'm → 1 $** · Ayirboshlash"
    assert ex.splitlines()[1] == "Kurs 12 800 · 2 yanvar"
    ru = format_transfer_card(
        amount=1000, currency="UZS", from_wallet_name="A", to_wallet_name="B",
        op_date=date(2026, 1, 2), from_balance=1, to_balance=2,
    )
    assert ru.splitlines()[0] == "↔️ **1 000 сум** · Перевод"


def test_keyboards_uz_and_ru_default() -> None:
    tid = uuid.uuid4()
    assert _buttons(card_keyboard(tid, "uz")) == ["Hamyon", "Tahrirlash", "O'chirish"]
    assert _buttons(card_keyboard(tid)) == ["Кошелёк", "Изменить", "Удалить"]
    assert _buttons(transfer_card_keyboard(tid, "uz")) == ["Tahrirlash", "O'chirish"]
    assert _buttons(transfer_card_keyboard(tid)) == ["Изменить", "Удалить"]
    assert _buttons(type_question_keyboard("p", "uz")) == ["Xarajat", "Daromad"]
    assert _buttons(type_question_keyboard("p")) == ["Потратил", "Получил"]


# ---------------------------------------------------------- errors and limits


def test_limit_and_error_texts_by_language() -> None:
    assert model_limit_text(50).startswith("Сегодня записано 50 операций")
    assert "50" in model_limit_text(50, "uz") and "Bugun" in model_limit_text(50, "uz")
    assert unparsed_limit_text(20, "uz").startswith("Bugun 20 ta xabar")
    assert currency_missing_text("USD").startswith("Кошелька в долларах")
    assert "dollar" in currency_missing_text("USD", "uz")
    assert "so'm" in currency_missing_text("UZS", "uz")
    for key in (
        "quick.too_long", "quick.too_many_ops", "quick.no_amount", "quick.model_fail",
        "quick.gone", "quick.type_question", "quick.exchange_rate_required",
        "quick.voice_not_recognized", "quick.receipt_unreadable",
    ):
        assert CATALOGUE[key]["ru"] != CATALOGUE[key]["uz"], key


async def test_no_amount_message_in_uzbek_and_russian(monkeypatch) -> None:
    class _Empty:
        async def parse(self, request):
            return ParseResponse(operations=[])

    async with rollback_session() as session:
        uz_user, _, _ = await _seeded_user(session, 9_620_010, "uz")
        ru_user, _, _ = await _seeded_user(session, 9_620_011, "ru")
        monkeypatch.setattr(
            "bot.quick_entry.handlers.async_session_factory", SessionFactory(session)
        )
        set_parser_override(_Empty())
        for user, expected in (
            (uz_user, t("uz", "quick.no_amount")),
            (ru_user, MSG_NO_AMOUNT),
        ):
            msg = _msg(user.telegram_id, "salom")
            await handle_quick_entry_text(msg, SimpleNamespace())
            msg.answer.assert_awaited_once_with(expected)
        assert "taksi 25 ming" in t("uz", "quick.no_amount")


async def test_too_long_message_in_uzbek(monkeypatch) -> None:
    async with rollback_session() as session:
        user, _, _ = await _seeded_user(session, 9_620_012, "uz")
        monkeypatch.setattr(
            "bot.quick_entry.handlers.async_session_factory", SessionFactory(session)
        )
        msg = _msg(user.telegram_id, "a" * 501)
        await handle_quick_entry_text(msg, SimpleNamespace())
        msg.answer.assert_awaited_once_with(t("uz", "quick.too_long"))


# ------------------------------------------------- reminder, digest, goals, release


async def test_evening_reminder_follows_language(api_client) -> None:  # noqa: F811
    _, session = api_client
    tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    owner, budget = await create_user_with_budget(session, telegram_id=tid, role="owner")
    owner.language = "uz"
    member = User(
        telegram_id=tid + 1, family_budget_id=budget.id, role="member", language="ru"
    )
    session.add(member)
    await session.flush()
    bot = AsyncMock()
    await send_evening_reminders_for_family(session, budget, date(2026, 8, 4), bot)
    sent = {c.args[0]: c.args[1] for c in bot.send_message.await_args_list}
    assert sent[owner.telegram_id] == t("uz", "reminder.evening")
    assert sent[member.telegram_id] == t("ru", "reminder.evening")
    assert "taksi" in sent[owner.telegram_id] or "bozorlik" in sent[owner.telegram_id]


async def test_weekly_digest_uzbek_with_translated_leader(api_client) -> None:  # noqa: F811
    _, session = api_client
    tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    owner, budget = await create_user_with_budget(session, telegram_id=tid, role="owner")
    owner.language = "uz"
    member = User(
        telegram_id=tid + 1, family_budget_id=budget.id, role="member", language="ru"
    )
    session.add(member)
    await copy_seed_categories_only(session, budget.id, legacy=True)
    wallet = Wallet(family_budget_id=budget.id, name="Карта сум", currency="UZS")
    session.add(wallet)
    await session.flush()
    food_sub = await session.scalar(
        select(ExpenseCategory).where(
            ExpenseCategory.family_budget_id == budget.id,
            ExpenseCategory.translation_key == "groceries",
        )
    )
    monday = date(2026, 8, 3)
    for amount, day in ((300_000, date(2026, 7, 29)), (100_000, date(2026, 7, 22))):
        session.add(
            Transaction(
                family_budget_id=budget.id, type="expense", wallet_id=wallet.id,
                amount=amount, expense_category_id=food_sub.id,
                created_by_user_id=owner.id,
                transaction_date=datetime(day.year, day.month, day.day, 12, tzinfo=TASHKENT),
            )
        )
    await session.flush()
    uz = await build_digest_body(session, budget.id, monday, language="uz")
    ru = await build_digest_body(session, budget.id, monday)
    assert uz.splitlines()[0] == "Hafta yakunlari"
    assert "Xarajatlar: 300 000 so'm" in uz
    assert "Eng ko'pi — Ovqat, 300 000 so'm" in uz and "Еда" not in uz
    assert ru.splitlines()[0] == "Итоги недели"
    assert "Расходы: 300 000 сум" in ru and "Больше всего — Еда" in ru
    bot = AsyncMock()
    await send_weekly_digest_for_family(session, budget, monday, bot)
    sent = {c.args[0]: c.args[1] for c in bot.send_message.await_args_list}
    assert sent[owner.telegram_id] == uz
    assert sent[member.telegram_id] == ru


def test_goal_achievement_text_and_button_languages() -> None:
    ru = format_achievement_message("Накопления", 8_200_000, 8_000_000, "UZS")
    assert ru == "🎯 Цель «Накопления» достигнута\nНакоплено 8 200 000 сум из 8 000 000"
    uz = format_achievement_message("Mashina", 8_200_000, 8_000_000, "UZS", "uz")
    assert uz == "🎯 «Mashina» maqsadiga erishildi\nYig'ildi: 8 200 000 so'm / 8 000 000"


async def test_goal_fan_out_each_member_in_own_language(api_client) -> None:  # noqa: F811
    from app.services.goal_notify import owner_close_keyboard

    _, session = api_client
    tid = int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000
    owner, budget = await create_user_with_budget(session, telegram_id=tid, role="owner")
    owner.language = "uz"
    member = User(
        telegram_id=tid + 1, family_budget_id=budget.id, role="member", language="ru"
    )
    session.add(member)
    wallet = Wallet(family_budget_id=budget.id, name="Цель", currency="UZS")
    session.add(wallet)
    await session.flush()
    goal = Goal(
        family_budget_id=budget.id, wallet_id=wallet.id, name="Mashina",
        target_amount=1_000_000, currency="UZS", status="active",
    )
    session.add(goal)
    await session.flush()
    bot = AsyncMock()
    await fan_out_achievement(session, goal, 1_000_000, bot)
    calls = {c.args[0]: c for c in bot.send_message.await_args_list}
    assert calls[owner.telegram_id].args[1].startswith("🎯 «Mashina» maqsadiga erishildi")
    assert _buttons(calls[owner.telegram_id].kwargs["reply_markup"]) == ["Maqsadni yopish"]
    assert calls[member.telegram_id].args[1].startswith("🎯 Цель «Mashina» достигнута")
    assert _buttons(owner_close_keyboard(goal.id)) == ["Закрыть цель"]


def test_release_announcement_languages() -> None:
    from app.services.release_announcement import RELEASE_ANNOUNCEMENT_TEXT

    assert release_announcement_text("ru") == RELEASE_ANNOUNCEMENT_TEXT
    assert "taksi 25 ming" in release_announcement_text("uz")


# --------------------------------------------------------------- cascade keywords


def _cats() -> tuple[list[PrefilterCategory], list[PrefilterCategory]]:
    expense, income = [], []
    for _name, key in SEED_INCOME_CATEGORIES:
        income.append(PrefilterCategory(uuid.uuid4(), _name, key, None))
    for parent_name, (parent_key, subs) in SEED_EXPENSE_CATEGORIES.items():
        pid = uuid.uuid4()
        expense.append(PrefilterCategory(pid, parent_name, parent_key, None))
        for sub_name, sub_key in subs:
            expense.append(PrefilterCategory(uuid.uuid4(), sub_name, sub_key, pid))
    return expense, income


def _prefilter_category_key(text: str):
    expense, income = _cats()
    result = try_prefilter(
        text, wallet_names=[], expense_categories=expense, income_categories=income
    )
    if result.operation is None:
        return result.reason, None
    name = result.operation.category
    pool = expense if result.operation.type == "expense" else income
    key = next((c.translation_key for c in pool if c.name == name), None)
    return key, result.operation.amount


UZ_PHRASES = [
    # (phrase, expected translation_key)
    ("taksiga 20000", "taxi"), ("yandex go 15000", "taxi"), ("indrive 18000", "taxi"),
    ("bolt 12000", "taxi"), ("такси 15000", "taxi"), ("индрайв 15000", "taxi"),
    ("benzinga 200000", "fuel"), ("zapravka 150000", "fuel"), ("бензин 100000", "fuel"),
    ("yoqilg'i 100000", "fuel"), ("dizel 300000", "fuel"),
    ("avtobusga 2000", "public_transport"), ("marshrutka 1500", "public_transport"),
    ("yo'l kira 2000", "public_transport"), ("метро 1400", "public_transport"),
    ("avtomoyka 30000", "car_maintenance"), ("avtoservis 400000", "car_maintenance"),
    ("moy almashtirish 150000", "car_maintenance"), ("автомойка 30000", "car_maintenance"),
    ("non 5000", "groceries"), ("go'sht 120000", "groceries"), ("sut 15000", "groceries"),
    ("meva 40000", "groceries"), ("supermarket 90000", "groceries"),
    ("бозорлик 100000", "groceries"), ("озиқ-овқат 100000", "groceries"),
    ("tushlik 35000", "cafes_restaurants"), ("nonushta 20000", "cafes_restaurants"),
    ("choyxona 80000", "cafes_restaurants"), ("oshxona 50000", "cafes_restaurants"),
    ("чойхона 80000", "cafes_restaurants"),
    ("wolt 60000", "delivery"), ("express24 55000", "delivery"), ("delivery 30000", "delivery"),
    ("ijaraga 3000000", "rent"), ("kvartira 4000000", "rent"), ("ижара 3000000", "rent"),
    ("suv 20000", "utilities"), ("tok 60000", "utilities"), ("kommunalka 300000", "utilities"),
    ("мусор 10000", "utilities"), ("elektr energiya 80000", "utilities"),
    ("uztelecom 90000", "telecom_internet"), ("mobil aloqa 20000", "telecom_internet"),
    ("ucell 30000", "telecom_internet"), ("интернет 100000", "telecom_internet"),
    ("tamir 500000", "repairs_furnishing"), ("ta'mirlash 500000", "repairs_furnishing"),
    ("santexnik 100000", "repairs_furnishing"), ("kafel 700000", "repairs_furnishing"),
    ("таъмир 500000", "repairs_furnishing"),
    ("bog'chaga 400000", "kindergarten_school"), ("maktabga 200000", "kindergarten_school"),
    ("kontrakt 5000000", "kindergarten_school"), ("litsey 300000", "kindergarten_school"),
    ("мактаб 200000", "kindergarten_school"),
    ("kurs 300000", "clubs_tutoring"), ("ustoz 200000", "clubs_tutoring"),
    ("репетитор 200000", "clubs_tutoring"),
    ("o'yinchoq 50000", "kids_goods"), ("pampers 120000", "kids_goods"),
    ("bolalar kiyimi 150000", "kids_goods"), ("kolyaska 800000", "kids_goods"),
    ("dorixona 50000", "pharmacy"), ("dorilar 70000", "pharmacy"),
    ("vitamin 40000", "pharmacy"), ("дори 50000", "pharmacy"),
    ("vrach 100000", "doctors_clinics"), ("kasalxona 200000", "doctors_clinics"),
    ("tahlil 90000", "doctors_clinics"), ("uzi 120000", "doctors_clinics"),
    ("poliklinika 30000", "doctors_clinics"), ("касалхона 200000", "doctors_clinics"),
    ("tishchi 300000", "dentistry"), ("plomba 150000", "dentistry"),
    ("стоматология 300000", "dentistry"), ("тишчи 300000", "dentistry"),
    ("to'yga 500000", "toi_celebrations"), ("nikoh 1000000", "toi_celebrations"),
    ("sunnat 400000", "toi_celebrations"), ("тўйга 500000", "toi_celebrations"),
    ("tug'ilgan kun 300000", "events_celebrations"), ("bayram 100000", "events_celebrations"),
    ("tadbir 200000", "events_celebrations"),
    ("guldasta 150000", "event_gifts"), ("sovga 100000", "event_gifts"),
    ("kiyim-kechak 300000", "clothing"), ("krossovka 400000", "clothing"),
    ("ko'ylak 150000", "clothing"), ("poyabzal 250000", "clothing"),
    ("кийим 300000", "clothing"),
    ("kinoga 60000", "entertainment"), ("teatr 80000", "entertainment"),
    ("konsert 200000", "entertainment"), ("karaoke 150000", "entertainment"),
    ("кино 60000", "entertainment"),
    ("youtube premium 30000", "subscriptions"), ("chatgpt 220000", "subscriptions"),
    ("icloud 15000", "subscriptions"), ("obunaga 20000", "subscriptions"),
    ("sartarosh 40000", "beauty_care"), ("manikyur 100000", "beauty_care"),
    ("kosmetika 200000", "beauty_care"), ("barber 70000", "beauty_care"),
    ("сартарош 40000", "beauty_care"),
    ("avans 2000000", "salary"), ("premiya 1000000", "salary"), ("bonus 500000", "salary"),
    ("maosh 5000000", "salary"), ("маош 5000000", "salary"),
    ("frilans 500000", "side_job"), ("podrabotka 300000", "side_job"),
    ("zakazdan 400000", "side_job"), ("фриланс 500000", "side_job"),
    ("hayitlik 200000", "gifts"), ("salomlik 500000", "gifts"),
    ("onamdan 500000", "family_transfers"), ("dadamdan 300000", "family_transfers"),
    ("ota-onamdan 400000", "family_transfers"), ("онамдан 500000", "family_transfers"),
    ("farzandlar 100000", "children"), ("bola 50000", "children"),
    ("davolanish 600000", "health"), ("саломатлик 100000", "health"),
]


@pytest.mark.parametrize(("phrase", "expected"), UZ_PHRASES)
def test_uzbek_keywords_resolve_to_category(phrase: str, expected: str) -> None:
    key, _ = _prefilter_category_key(phrase)
    assert key == expected, (phrase, key)


def test_every_default_category_has_latin_and_cyrillic_uzbek_terms() -> None:
    import re

    cyr = re.compile(r"[Ѐ-ӿ]")
    skip = {"income_other"}
    for key in build_seed_name_by_key():
        if key in skip or key in {"card_uzs", "cash_uzs", "card_usd", "cash_usd"}:
            continue
        terms = CASCADE_KEYWORDS.get(key, [])
        assert terms, f"{key}: no cascade keywords"
        assert any(not cyr.search(x) for x in terms), f"{key}: no Latin term"
    # Cyrillic-Uzbek (not just Russian) terms exist for the main categories
    for key in ("groceries", "taxi", "fuel", "rent", "utilities", "pharmacy", "clothing"):
        assert any(cyr.search(x) for x in CASCADE_KEYWORDS[key]), key


@pytest.mark.parametrize(
    "phrase",
    [
        "taksi 25 ming", "taksi 25 mingga", "taksi 25k",
        "taksi 25 К", "taksi 25 минг",
    ],
)
def test_uzbek_thousand_word_is_not_read_as_25(phrase: str) -> None:
    key, amount = _prefilter_category_key(phrase)
    if key == "taxi":
        assert amount == 25_000
    else:
        # anything we do not understand must fall through to the model, never record 25
        assert amount is None


def test_taksi_25_ming_and_million() -> None:
    assert _prefilter_category_key("taksi 25 ming") == ("taxi", 25_000)
    assert _prefilter_category_key("taksi 25 минг") == ("taxi", 25_000)
    assert _prefilter_category_key("taksi 25k") == ("taxi", 25_000)
    assert _prefilter_category_key("ijara 3 mln") == ("rent", 3_000_000)
    assert _prefilter_category_key("ijara 3 million") == ("rent", 3_000_000)
    assert _prefilter_category_key("такси 25 тысяч") == ("taxi", 25_000)
    assert _prefilter_category_key("taksi 25000") == ("taxi", 25_000)


def test_typographic_apostrophes_match_keywords() -> None:
    for apos in ("’", "ʼ", "ʻ", "‘"):
        assert _prefilter_category_key(f"to{apos}yga 500000")[0] == "toi_celebrations"
        assert _prefilter_category_key(f"yoqilg{apos}i 100000")[0] == "fuel"


def test_new_uz_keys_exist_with_ascii_apostrophe() -> None:
    for key in CATALOGUE:
        if key.startswith(("quick.", "card.", "reminder.", "digest.", "goal.", "release.", "month.")):
            assert CATALOGUE[key]["uz"].strip()
            for bad in ("’", "ʻ", "ʼ", "‘"):
                assert bad not in CATALOGUE[key]["uz"]
