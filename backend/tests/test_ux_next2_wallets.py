"""ux-next2 (QA bugs 5, 6, 7): wallet name inside other words, two equal cards, word forms, transfer direction."""
import pytest
from sqlalchemy import select

from app.models.transaction import Transaction

from app.parsing.stub import StubParser
from app.parsing.types import ParsedOperation
from app.services.quick_entry_transfer import resolve_transfer_wallets
from app.services.quick_entry_wallets import resolve_wallet, strip_wallet_mention
from bot.quick_entry.handlers import handle_quick_entry_text, set_parser_override
from tests.test_ux_r15_wallet_pick import (
    FailingParser,
    FixedParser,
    SessionFactory,
    _add_taxi,
    _last_txn,
    _message,
    _reset_parser,  # noqa: F401  (autouse fixture)
    rollback_session,
    setup_family,
)
from types import SimpleNamespace

pytestmark = pytest.mark.anyio


# ---- 5: only the whole word is cut from the comment
@pytest.mark.parametrize(
    "comment,name,hint,expected",
    [
        ("такси на канал 20000 Нал", "Нал", "Нал", "такси на канал 20000"),
        ("налево такси Нал", "Нал", "Нал", "налево такси"),
        ("оплата канала Нал", "Нал", "нал", "оплата канала"),
        ("non uyga Uy", "Uy", "Uy", "non uyga"),
        ("такси Карта сум", "Карта сум", "Карта сум", "такси"),
        ("такси картой", "Карта", "картой", "такси"),
        ("такси с карты", "Карта", "карты", "такси"),
    ],
)
def test_strip_cuts_only_whole_words(comment, name, hint, expected) -> None:
    assert strip_wallet_mention(comment, name, hint) == expected


async def _send(monkeypatch, wallets, default, text, parser=None, language="ru"):
    async with rollback_session() as session:
        user, budget, by_name = await setup_family(session, wallets, default, language=language)
        await _add_taxi(session, budget)
        set_parser_override(parser or FailingParser())
        monkeypatch.setattr(
            "bot.quick_entry.handlers.async_session_factory", SessionFactory(session)
        )
        await handle_quick_entry_text(_message(user.telegram_id, text), SimpleNamespace())
        txn = await _last_txn(session, budget)
        assert txn is not None
        wallet_name = next(n for n, w in by_name.items() if w.id == txn.wallet_id)
        return wallet_name, txn.comment


async def test_comment_keeps_words_that_only_contain_the_wallet_name(monkeypatch) -> None:
    wallets = [("Карта", "UZS", False), ("Нал", "UZS", False)]
    name, comment = await _send(monkeypatch, wallets, "Карта", "такси на канал 20000 Нал")
    assert name == "Нал"
    assert "канал" in (comment or "")


async def test_ai_path_comment_keeps_longer_words(monkeypatch) -> None:
    wallets = [("Карта", "UZS", False), ("Нал", "UZS", False)]
    op = ParsedOperation(type="expense", amount=30000, currency="UZS", wallet_hint="нал",
                         category="Такси", comment="такси на канал нал")
    name, comment = await _send(monkeypatch, wallets, "Карта", "такси на канал 30000 нал", FixedParser(op))
    assert name == "Нал"
    assert "канал" in (comment or "") and "ка " not in f"{comment} "


# ---- 6: two cards, one per currency
TWO_CARDS_CUR = [("Наличные", "UZS", False), ("Карта", "UZS", False), ("Карта", "USD", False)]


async def test_equal_names_resolved_by_amount_currency() -> None:
    async with rollback_session() as session:
        user, budget, _ = await setup_family(session, [("Наличные", "UZS", False)], "Наличные")
        from app.models.wallet import Wallet
        uzs = Wallet(family_budget_id=budget.id, name="Карта", currency="UZS", is_personal=False)
        usd = Wallet(family_budget_id=budget.id, name="Карта", currency="USD", is_personal=False)
        session.add_all([uzs, usd])
        await session.flush()
        cash = (await session.get(type(uzs), user.default_wallet_id))
        for cur, exp in (("UZS", uzs), ("USD", usd)):
            got = await resolve_wallet(session=session, family_budget_id=budget.id, writer=user,
                                       wallet_hint="карты", currency=cur, default_wallet=cash)
            assert got.id == exp.id
        got = await resolve_wallet(session=session, family_budget_id=budget.id, writer=user,
                                   wallet_hint="карты", currency=None, default_wallet=cash)
        assert got.id == uzs.id  # no currency in the phrase: the default wallet's (UZS) decides


async def test_handler_two_cards_picks_by_currency_of_amount(monkeypatch) -> None:
    async with rollback_session() as session:
        user, budget, by_name = await setup_family(session, [("Наличные", "UZS", False)], "Наличные")
        from app.models.wallet import Wallet
        uzs = Wallet(family_budget_id=budget.id, name="Карта", currency="UZS", is_personal=False)
        usd = Wallet(family_budget_id=budget.id, name="Карта", currency="USD", is_personal=False)
        session.add_all([uzs, usd])
        await session.flush()
        await _add_taxi(session, budget)
        set_parser_override(FixedParser(ParsedOperation(
            type="expense", amount=20000, currency="UZS", wallet_hint="карты",
            category="Такси", comment="такси с карты")))
        import bot.quick_entry.handlers as h
        monkeypatch.setattr(h, "async_session_factory", SessionFactory(session))
        await handle_quick_entry_text(_message(user.telegram_id, "такси 20000 сум с карты"), SimpleNamespace())
        txn = await _last_txn(session, budget)
        assert txn.wallet_id == uzs.id
        set_parser_override(FixedParser(ParsedOperation(
            type="expense", amount=20, currency="USD", wallet_hint="карты",
            category="Такси", comment="такси с карты")))
        await handle_quick_entry_text(_message(user.telegram_id, "такси 20 долларов с карты"), SimpleNamespace())
        txn = (await session.scalars(select(Transaction).where(
            Transaction.family_budget_id == budget.id, Transaction.amount == 20))).one()
        assert txn.wallet_id == usd.id


# ---- 7: word forms on the quick (prefilter) path, same result as the AI path
NAMES_RU = [("Наличный сум", "UZS", False), ("Карта сум", "UZS", False)]
NAMES_LAT = [("Naqd", "UZS", False), ("Karta", "UZS", False), ("Humo", "UZS", False)]
PREFILTER_TABLE = [
    ("такси 20000 картой", NAMES_RU, "Наличный сум", "Карта сум"),
    ("такси 20000 карту", NAMES_RU, "Наличный сум", "Карта сум"),
    ("такси 20000 наличными", NAMES_RU, "Карта сум", "Наличный сум"),
    ("taksi 20000 humodan", NAMES_LAT, "Naqd", "Humo"),
    ("такси 20000 humodan", NAMES_LAT, "Naqd", "Humo"),
    ("такси 20000 kartadan", NAMES_RU, "Наличный сум", "Карта сум"),
    ("такси 20000 naqd", NAMES_RU, "Карта сум", "Наличный сум"),
    ("такси 20000 naqdda", NAMES_RU, "Карта сум", "Наличный сум"),
]


@pytest.mark.parametrize("text,wallets,default,expected", PREFILTER_TABLE)
async def test_prefilter_path_picks_inflected_wallet(monkeypatch, text, wallets, default, expected) -> None:
    name, comment = await _send(monkeypatch, wallets, default, text)
    assert name == expected
    low = (comment or "").casefold()
    for bad in ("карт", "налич", "humo", "kart", "naqd"):
        assert bad not in low


@pytest.mark.parametrize("text,wallets,default,expected", PREFILTER_TABLE)
async def test_ai_path_gives_the_same_wallet(monkeypatch, text, wallets, default, expected) -> None:
    hint = text.split()[-1]
    op = ParsedOperation(type="expense", amount=20000, currency=None, wallet_hint=hint,
                         category="Такси", comment=text)
    name, _ = await _send(monkeypatch, wallets, default, "поехал " + text + " ок", FixedParser(op))
    assert name == expected


TRANSFER_PHRASES = [
    ("kartadan", "naqdga", "Карта сум", "Наличный сум"),
    ("naqddan", "kartaga", "Наличный сум", "Карта сум"),
    ("с карты", "на наличные", "Карта сум", "Наличный сум"),
    ("с наличных", "на карту", "Наличный сум", "Карта сум"),
    ("из карты", "в наличные", "Карта сум", "Наличный сум"),
    ("от наличных", "на карту", "Наличный сум", "Карта сум"),
    # the model put the two hints the wrong way round: the case ending / preposition decides
    ("naqdga", "kartadan", "Карта сум", "Наличный сум"),
    ("на наличные", "с карты", "Карта сум", "Наличный сум"),
    ("kartaga", "naqddan", "Наличный сум", "Карта сум"),
    # mixed scripts
    ("kartadan", "на наличные", "Карта сум", "Наличный сум"),
    ("с карты", "naqdga", "Карта сум", "Наличный сум"),
]


@pytest.mark.parametrize("frm,to,exp_from,exp_to", TRANSFER_PHRASES)
async def test_transfer_direction_by_prepositions_and_endings(frm, to, exp_from, exp_to) -> None:
    async with rollback_session() as session:
        for default in ("Наличный сум", "Карта сум"):
            user, budget, by_name = await setup_family(session, NAMES_RU, default)
            got = await resolve_transfer_wallets(
                session=session, family_budget_id=budget.id, writer=user,
                from_hint=frm, to_hint=to, amount_currency="UZS",
                default_wallet=by_name[default])
            assert (got.from_wallet.name, got.to_wallet.name) == (exp_from, exp_to)
