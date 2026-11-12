"""r15: a wallet is picked only by its full name or a distinguishing word of it."""
import socket
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine
from app.models.expense_category import ExpenseCategory
from app.models.family_budget import FamilyBudget
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.parsing.stub import StubParser
from app.parsing.types import ParseResponse, ParsedOperation
from app.services.quick_entry_transfer import resolve_transfer_wallets
from app.services.quick_entry_wallets import resolve_wallet
from bot.quick_entry.handlers import handle_quick_entry_text, set_parser_override
from tests.db_helpers import db_address


def _db_available() -> bool:
    try:
        with socket.create_connection(db_address(), timeout=1):
            return True
    except OSError:
        return False


@asynccontextmanager
async def rollback_session() -> AsyncIterator[AsyncSession]:
    await engine.dispose()
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            yield session
        finally:
            await trans.rollback()
            await session.close()


pytestmark = [
    pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available"),
    pytest.mark.anyio,
]

_tg = [9_150_000]


async def setup_family(session, wallets, default_name, *, language="ru"):
    """wallets: list of (name, currency, personal). Returns user, budget, {name: Wallet}."""
    _tg[0] += 1
    budget = FamilyBudget(invite_token=f"test-{uuid.uuid4()}")
    session.add(budget)
    await session.flush()
    user = User(telegram_id=_tg[0], family_budget_id=budget.id, role="owner", language=language)
    session.add(user)
    await session.flush()
    by_name: dict[str, Wallet] = {}
    for name, cur, personal in wallets:
        w = Wallet(
            family_budget_id=budget.id,
            name=name,
            currency=cur,
            is_personal=personal,
            owner_user_id=user.id if personal else None,
        )
        session.add(w)
        await session.flush()
        by_name[name] = w
    user.default_wallet_id = by_name[default_name].id
    await session.flush()
    return user, budget, by_name


CASH_CARD = [("Наличный сум", "UZS", False), ("Карта сум", "UZS", False)]
LATIN = [("Naqd", "UZS", False), ("Karta", "UZS", False)]
WITH_USD = [
    ("Наличный сум", "UZS", False),
    ("Карта сум", "UZS", False),
    ("Карта USD", "USD", False),
]
FOUR = [
    ("Наличный сум", "UZS", False),
    ("Карта сум", "UZS", False),
    ("Наличный USD", "USD", False),
    ("Карта USD", "USD", False),
]
TWO_CARDS = [("Карта Humo", "UZS", False), ("Карта Uzcard", "UZS", False), ("Наличные", "UZS", False)]
PERSONAL = [("Общий", "UZS", False), ("Моя карта", "UZS", True)]

# (wallets, default, hint, currency, expected wallet name)
HINT_TABLE = [
    # full name wins over the shared word "сум"
    (CASH_CARD, "Наличный сум", "Карта сум", None, "Карта сум"),
    (CASH_CARD, "Карта сум", "Наличный сум", None, "Наличный сум"),
    (CASH_CARD, "Карта сум", "наличные сум", None, "Наличный сум"),
    # generic words alone never select
    (CASH_CARD, "Карта сум", "сум", None, "Карта сум"),
    (CASH_CARD, "Наличный сум", "so'm", None, "Наличный сум"),
    (CASH_CARD, "Наличный сум", "доллар", None, "Наличный сум"),
    # distinguishing part, cases
    (CASH_CARD, "Наличный сум", "карта", None, "Карта сум"),
    (CASH_CARD, "Наличный сум", "С КАРТЫ", None, "Карта сум"),
    (CASH_CARD, "Карта сум", "наличными", None, "Наличный сум"),
    # Latin names, suffixes
    (LATIN, "Naqd", "Karta", None, "Karta"),
    (LATIN, "Naqd", "kartadan", None, "Karta"),
    (LATIN, "Karta", "naqddan", None, "Naqd"),
    (LATIN, "Karta", "NAQD", None, "Naqd"),
    # USD wallet
    (WITH_USD, "Наличный сум", "Карта USD", None, "Карта USD"),
    (WITH_USD, "Наличный сум", "карта доллара", None, "Карта USD"),
    (WITH_USD, "Наличный сум", "Карта сум", None, "Карта сум"),
    # "карта" is shared by two cards: not guessed, default wallet is used
    (TWO_CARDS, "Наличные", "карта", None, "Наличные"),
    (TWO_CARDS, "Наличные", "Карта Humo", None, "Карта Humo"),
    (TWO_CARDS, "Наличные", "с uzcard", None, "Карта Uzcard"),
    # a card per currency: the amount's currency decides, without it the default is kept
    (FOUR, "Наличный сум", "карта", "USD", "Карта USD"),
    (FOUR, "Наличный USD", "карта", "UZS", "Карта сум"),
    (FOUR, "Наличный сум", "карта", None, "Наличный сум"),
    # personal wallet of the writer
    (PERSONAL, "Общий", "моя карта", None, "Моя карта"),
    (PERSONAL, "Общий", "карта", None, "Моя карта"),
]


@pytest.mark.parametrize("wallets,default,hint,currency,expected", HINT_TABLE)
async def test_resolve_wallet_by_hint(wallets, default, hint, currency, expected) -> None:
    async with rollback_session() as session:
        user, budget, by_name = await setup_family(session, wallets, default)
        got = await resolve_wallet(
            session=session,
            family_budget_id=budget.id,
            writer=user,
            wallet_hint=hint,
            currency=currency,
            default_wallet=by_name[default],
        )
        assert got.name == expected


TRANSFER_TABLE = [
    (CASH_CARD, "Карта", "Наличные", "Карта сум", "Наличный сум"),
    (CASH_CARD, "с карты сум", "на наличный сум", "Карта сум", "Наличный сум"),
    (CASH_CARD, "Наличный сум", "Карта сум", "Наличный сум", "Карта сум"),
    (LATIN, "kartadan", "naqdga", "Karta", "Naqd"),
    (LATIN, "naqddan", "kartaga", "Naqd", "Karta"),
]


@pytest.mark.parametrize("wallets,frm,to,exp_from,exp_to", TRANSFER_TABLE)
async def test_transfer_wallets_by_hint(wallets, frm, to, exp_from, exp_to) -> None:
    async with rollback_session() as session:
        first = wallets[0][0]
        user, budget, by_name = await setup_family(session, wallets, first)
        got = await resolve_transfer_wallets(
            session=session,
            family_budget_id=budget.id,
            writer=user,
            from_hint=frm,
            to_hint=to,
            amount_currency="UZS",
            default_wallet=by_name[first],
        )
        assert (got.from_wallet.name, got.to_wallet.name) == (exp_from, exp_to)


class FailingParser(StubParser):
    async def parse(self, request):  # type: ignore[no-untyped-def]
        pytest.fail("parser.parse must not be called on prefilter hit")


class FixedParser(StubParser):
    def __init__(self, op: ParsedOperation) -> None:
        self._op = op
        self.wallet_names: list[str] | None = None

    async def parse(self, request):  # type: ignore[no-untyped-def]
        self.wallet_names = list(request.wallet_names)
        return ParseResponse(operations=[self._op])


class SessionFactory:
    def __init__(self, session):
        self._session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *_a):
        return None


def _message(tg: int, text: str):
    return SimpleNamespace(from_user=SimpleNamespace(id=tg), text=text, answer=AsyncMock())


async def _add_taxi(session, budget):
    transport = ExpenseCategory(
        family_budget_id=budget.id, name="Транспорт", translation_key="transport"
    )
    session.add(transport)
    await session.flush()
    session.add(
        ExpenseCategory(
            family_budget_id=budget.id,
            name="Такси",
            parent_id=transport.id,
            translation_key="taxi",
        )
    )
    await session.flush()


async def _last_txn(session, budget):
    return (
        await session.scalars(
            select(Transaction)
            .where(Transaction.family_budget_id == budget.id)
            .order_by(Transaction.created_at.desc())
        )
    ).first()


@pytest.fixture(autouse=True)
def _reset_parser():
    set_parser_override(None)
    yield
    set_parser_override(None)


TEXT_TABLE = [
    # text, wallets, default, expected wallet
    ("такси 20000 Карта сум", CASH_CARD, "Наличный сум", "Карта сум"),
    ("такси 20000 Наличный сум", CASH_CARD, "Карта сум", "Наличный сум"),
    ("такси 20000 сум", CASH_CARD, "Карта сум", "Карта сум"),
    ("такси 20000 карта сум", CASH_CARD, "Наличный сум", "Карта сум"),
    ("такси 15000 Karta", LATIN, "Naqd", "Karta"),
]


@pytest.mark.parametrize("text,wallets,default,expected", TEXT_TABLE)
async def test_text_entry_books_to_named_wallet_without_name_in_comment(
    monkeypatch, text, wallets, default, expected
) -> None:
    async with rollback_session() as session:
        user, budget, by_name = await setup_family(session, wallets, default)
        await _add_taxi(session, budget)
        set_parser_override(FailingParser())
        monkeypatch.setattr("bot.quick_entry.handlers.async_session_factory", SessionFactory(session))
        await handle_quick_entry_text(_message(user.telegram_id, text), SimpleNamespace())
        txn = await _last_txn(session, budget)
        assert txn is not None
        assert txn.wallet_id == by_name[expected].id
        comment = (txn.comment or "").casefold()
        for name in by_name:
            assert name.casefold() not in comment
        assert "karta" not in comment and "карта" not in comment


async def test_text_entry_two_equal_cards_not_guessed(monkeypatch) -> None:
    async with rollback_session() as session:
        user, budget, by_name = await setup_family(session, TWO_CARDS, "Наличные")
        await _add_taxi(session, budget)
        set_parser_override(FixedParser(ParsedOperation(
            type="expense", amount=20000, currency=None, wallet_hint="карта",
            category="Такси", comment="такси карта",
        )))
        monkeypatch.setattr("bot.quick_entry.handlers.async_session_factory", SessionFactory(session))
        await handle_quick_entry_text(_message(user.telegram_id, "такси 20000 с карты"), SimpleNamespace())
        txn = await _last_txn(session, budget)
        assert txn.wallet_id == by_name["Наличные"].id


async def test_ai_path_wallet_and_comment(monkeypatch) -> None:
    async with rollback_session() as session:
        user, budget, by_name = await setup_family(session, CASH_CARD, "Наличный сум")
        await _add_taxi(session, budget)
        parser = FixedParser(ParsedOperation(
            type="expense", amount=20000, currency=None, wallet_hint="Карта сум",
            category="Такси", comment="Такси Карта сум",
        ))
        set_parser_override(parser)
        monkeypatch.setattr("bot.quick_entry.handlers.async_session_factory", SessionFactory(session))
        await handle_quick_entry_text(
            _message(user.telegram_id, "поехал на такси, заплатил 20000 с карты сум"),
            SimpleNamespace(),
        )
        txn = await _last_txn(session, budget)
        assert txn.wallet_id == by_name["Карта сум"].id
        assert "карта" not in (txn.comment or "").casefold()
