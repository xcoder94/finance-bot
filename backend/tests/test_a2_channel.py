"""a-2: the operation channel is written on EVERY creation path (work/db/admin-schema.md §2.2 / W4).

Values: text / voice / photo (bot) and app (mini-app forms, manual purchase sum); NULL = before tracking.
Real Postgres, real aiogram Dispatcher/Update/Bot objects and the real HTTP app; only the AI parser
and the Telegram network are replaced at the outer boundary (shared helpers from the m3-4 tests).
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.expense_category import ExpenseCategory
from app.models.quick_entry_pending import QuickEntryPending
from app.models.transaction import Transaction
from app.models.wallet import Wallet
from app.parsing.types import ParseResponse, ParsedOperation
from bot.quick_entry.handlers import handle_quick_entry_type, set_parser_override
from bot.quick_entry.receipt_photo import set_receipt_parser_override
from tests.test_m3_4_bot_pending import (  # noqa: F401  (autouse fixture + helpers)
    PHOTO,
    VOICE,
    FixedParser,
    _env,
    expense,
    feed,
    open_pending,
    setup_family,
)
from tests.test_quick_entry_flow import (
    SessionFactory,
    make_callback,
    make_wallet,
    pytestmark,  # noqa: F401
    rollback_session,
)
from tests.test_shopping import add_items, buy, headers, make_family
from tests.test_shopping import api_client  # noqa: F401
from tests.test_shopping_pending import create_pending, hints  # noqa: F401
from tests.test_shopping_pending import _flag_on_and_hint_recorder  # noqa: F401

TEXT = {"text": "что-то 25000"}


def _ok(*ops: ParsedOperation, **kw) -> ParseResponse:
    return ParseResponse(operations=list(ops), **kw)


def _transfer_op() -> ParsedOperation:
    return ParsedOperation(
        type="transfer", amount=100_000, currency="UZS", wallet_hint=None, category=None,
        comment=None, from_wallet_hint="Карта сум", to_wallet_hint="Наличный сум",
    )


async def _with_cash_wallet(session, budget) -> None:
    session.add(make_wallet(budget, name="Наличный сум"))
    await session.flush()


async def _only_txn(session, budget, type_: str) -> Transaction:
    rows = (
        await session.scalars(
            select(Transaction).where(
                Transaction.family_budget_id == budget.id, Transaction.type == type_
            )
        )
    ).all()
    assert len(rows) == 1, rows
    return rows[0]


# ---- bot text -------------------------------------------------------------------------------


class TestBotText:
    async def test_expense(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, _ = await setup_family(session, 9_520_001)
            set_parser_override(FixedParser(_ok(expense(25_000))))
            await feed(monkeypatch, session, user.telegram_id, **TEXT)
            assert (await _only_txn(session, budget, "expense")).channel == "text"

    async def test_income(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, _ = await setup_family(session, 9_520_002)
            set_parser_override(FixedParser(_ok(expense(25_000, type_="income"))))
            await feed(monkeypatch, session, user.telegram_id, **TEXT)
            assert (await _only_txn(session, budget, "income")).channel == "text"

    async def test_transfer(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, _ = await setup_family(session, 9_520_003)
            await _with_cash_wallet(session, budget)
            set_parser_override(FixedParser(_ok(_transfer_op())))
            await feed(monkeypatch, session, user.telegram_id, **TEXT)
            assert (await _only_txn(session, budget, "transfer")).channel == "text"

    async def test_ambiguous_pending_and_confirm_keep_text(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, _ = await setup_family(session, 9_520_004)
            set_parser_override(FixedParser(_ok(expense(25_000, type_="ambiguous"))))
            await feed(monkeypatch, session, user.telegram_id, **TEXT)
            pending = await session.scalar(
                select(QuickEntryPending).where(QuickEntryPending.user_id == user.id)
            )
            assert pending.channel == "text"
            await _tap_type(monkeypatch, session, user, pending, "expense")
            assert (await _only_txn(session, budget, "expense")).channel == "text"


async def _tap_type(monkeypatch, session, user, pending, choice: str) -> None:
    monkeypatch.setattr(
        "bot.quick_entry.handlers.async_session_factory", SessionFactory(session)
    )
    callback = make_callback(
        telegram_id=user.telegram_id, data=f"qe:type:{pending.id}:{choice}"
    )
    await handle_quick_entry_type(callback, SimpleNamespace())


# ---- bot voice ------------------------------------------------------------------------------


class TestBotVoice:
    def _voice(self, *ops: ParsedOperation) -> FixedParser:
        return FixedParser(_ok(*ops, speech_status="recognized"))

    async def test_expense(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, _ = await setup_family(session, 9_521_001)
            set_parser_override(self._voice(expense(25_000)))
            await feed(monkeypatch, session, user.telegram_id, **VOICE)
            assert (await _only_txn(session, budget, "expense")).channel == "voice"

    async def test_income(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, _ = await setup_family(session, 9_521_002)
            set_parser_override(self._voice(expense(25_000, type_="income")))
            await feed(monkeypatch, session, user.telegram_id, **VOICE)
            assert (await _only_txn(session, budget, "income")).channel == "voice"

    async def test_transfer(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, _ = await setup_family(session, 9_521_003)
            await _with_cash_wallet(session, budget)
            set_parser_override(self._voice(_transfer_op()))
            await feed(monkeypatch, session, user.telegram_id, **VOICE)
            assert (await _only_txn(session, budget, "transfer")).channel == "voice"

    async def test_ambiguous_pending_and_confirm_keep_voice(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, _ = await setup_family(session, 9_521_004)
            set_parser_override(self._voice(expense(25_000, type_="ambiguous")))
            await feed(monkeypatch, session, user.telegram_id, **VOICE)
            pending = await session.scalar(
                select(QuickEntryPending).where(QuickEntryPending.user_id == user.id)
            )
            assert pending.channel == "voice"
            await _tap_type(monkeypatch, session, user, pending, "income")
            assert (await _only_txn(session, budget, "income")).channel == "voice"


    async def test_voice_pending_confirmed_as_expense_keeps_voice(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, _ = await setup_family(session, 9_521_005)
            set_parser_override(self._voice(expense(25_000, type_="ambiguous")))
            await feed(monkeypatch, session, user.telegram_id, **VOICE)
            pending = await session.scalar(
                select(QuickEntryPending).where(QuickEntryPending.user_id == user.id)
            )
            await _tap_type(monkeypatch, session, user, pending, "expense")
            assert (await _only_txn(session, budget, "expense")).channel == "voice"


# ---- bot photo (receipt) --------------------------------------------------------------------


class TestBotPhoto:
    async def test_receipt_expense(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, _ = await setup_family(session, 9_522_001)
            set_receipt_parser_override(
                FixedParser(_ok(expense(42_500), receipt_status="ok"))
            )
            await feed(monkeypatch, session, user.telegram_id, **PHOTO)
            assert (await _only_txn(session, budget, "expense")).channel == "photo"


# ---- purchase closed through the bot: channel = how the sum arrived --------------------------


class TestBotPurchase:
    async def test_bare_number_text(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_523_001)
            await open_pending(session, user, ids, "voice")
            await feed(monkeypatch, session, user.telegram_id, text="412000")
            assert (await _only_txn(session, budget, "expense")).channel == "text"

    async def test_text_sum_through_parser(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_523_002)
            await open_pending(session, user, ids, "receipt")
            set_parser_override(FixedParser(_ok(expense(412_000, type_="ambiguous"))))
            await feed(monkeypatch, session, user.telegram_id, text="четыреста двенадцать тысяч")
            assert (await _only_txn(session, budget, "expense")).channel == "text"

    async def test_voice_sum(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_523_003)
            await open_pending(session, user, ids, "voice")
            set_parser_override(
                FixedParser(_ok(expense(412_000, type_="ambiguous"), speech_status="recognized"))
            )
            await feed(monkeypatch, session, user.telegram_id, **VOICE)
            assert (await _only_txn(session, budget, "expense")).channel == "voice"

    async def test_photo_total(self, monkeypatch) -> None:
        async with rollback_session() as session:
            user, budget, ids = await setup_family(session, 9_523_004)
            await open_pending(session, user, ids, "receipt")
            set_receipt_parser_override(FixedParser(_ok(expense(412_000), receipt_status="ok")))
            await feed(monkeypatch, session, user.telegram_id, **PHOTO)
            assert (await _only_txn(session, budget, "expense")).channel == "photo"


# ---- mini-app (REST) ------------------------------------------------------------------------


def _payload(**kw) -> dict:
    return {"transaction_date": "2026-06-15T07:00:00+00:00", "amount": 1000, **kw}


class TestApp:
    async def _fam(self, session):
        fam = await make_family(session)
        second = make_wallet(fam["budget"], name="Вторая")
        usd = Wallet(family_budget_id=fam["budget"].id, name="Доллары", currency="USD")
        session.add_all([second, usd])
        await session.flush()
        return fam, second, usd

    async def test_income_expense_transfer_exchange_forms(self, api_client) -> None:
        client, session = api_client
        fam, second, usd = await self._fam(session)
        h = headers(fam["user"].telegram_id)
        inc_cat = await _income_category(session, fam["budget"])
        r = await client.post(
            "/api/v1/transactions/income", headers=h,
            json=_payload(wallet_id=str(fam["wallet"].id), income_category_id=str(inc_cat.id)),
        )
        assert r.status_code == 201, r.text
        r = await client.post(
            "/api/v1/transactions/expense", headers=h,
            json=_payload(wallet_id=str(fam["wallet"].id), expense_category_id=str(fam["groceries"].id)),
        )
        assert r.status_code == 201, r.text
        r = await client.post(
            "/api/v1/transactions/transfer", headers=h,
            json=_payload(wallet_id=str(fam["wallet"].id), to_wallet_id=str(second.id)),
        )
        assert r.status_code == 201, r.text
        r = await client.post(  # exchange = transfer between currencies
            "/api/v1/transactions/transfer", headers=h,
            json=_payload(wallet_id=str(fam["wallet"].id), to_wallet_id=str(usd.id), rate=12500),
        )
        assert r.status_code == 201, r.text
        rows = (
            await session.scalars(
                select(Transaction).where(Transaction.family_budget_id == fam["budget"].id)
            )
        ).all()
        assert sorted(t.type for t in rows) == ["expense", "income", "transfer", "transfer"]
        assert {t.channel for t in rows} == {"app"}

    async def test_manual_purchase_sum(self, api_client) -> None:
        client, session = api_client
        fam = await make_family(session)
        tid = fam["user"].telegram_id
        items = await add_items(client, tid, "молоко")
        r = await buy(client, tid, [items[0]["id"]], amount=50_000)
        assert r.status_code == 201, r.text
        tx = await session.get(Transaction, uuid.UUID(r.json()["transaction_id"]))
        assert tx.channel == "app"

    async def test_pending_purchase_manual_sum_in_app(self, api_client, hints) -> None:
        client, session = api_client
        fam = await make_family(session)
        tid = fam["user"].telegram_id
        items = await add_items(client, tid, "молоко", "хлеб")
        pid = (await create_pending(client, tid, [i["id"] for i in items], "voice")).json()["id"]
        r = await client.post(
            f"/api/v1/shopping/purchases/pending/{pid}/amount", headers=headers(tid),
            json={"amount": 412_000},
        )
        assert r.status_code == 201, r.text
        tx = await session.get(Transaction, uuid.UUID(r.json()["transaction_id"]))
        assert tx.channel == "app"


async def _income_category(session, budget):
    from app.models.income_category import IncomeCategory

    cat = IncomeCategory(family_budget_id=budget.id, name="Зарплата")
    session.add(cat)
    await session.flush()
    return cat
