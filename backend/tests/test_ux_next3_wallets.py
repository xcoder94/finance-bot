"""ux-next3 (QA round 3): one wallet-mention rule for the quick path and the AI path."""
import pytest
from sqlalchemy import select

from app.models.transaction import Transaction
from app.models.wallet import Wallet
from app.parsing.types import ParsedOperation
from app.services.quick_entry_transfer import resolve_transfer_wallets
from bot.quick_entry.handlers import handle_quick_entry_text, set_parser_override
from tests.test_ux_next2_wallets import _send
from tests.test_ux_r15_wallet_pick import (
    FailingParser,
    FixedParser,
    SessionFactory,
    _add_taxi,
    _message,
    _reset_parser,  # noqa: F401  (autouse fixture)
    rollback_session,
    setup_family,
)
from types import SimpleNamespace

pytestmark = pytest.mark.anyio

# ---- 1: a wallet whose own name ends like a case ending is just a name
RU_SET = ["Карта", "Копилка", "Наличка"]
UZ_SET = ["Karta", "Kopilka", "Yoga", "Buqa", "Sara"]  # -ka, -ga, -qa, -ra


def _transfer_cases():
    for names in (RU_SET, UZ_SET):
        card = names[0]
        for other in names[1:]:
            yield names, other, card, f"{other}", f"{card}"
            yield names, card, other, f"{card}", f"{other}"


@pytest.mark.parametrize("names,src,dst,frm,to", list(_transfer_cases()))
async def test_plain_names_keep_the_direction_the_model_gave(names, src, dst, frm, to) -> None:
    async with rollback_session() as session:
        for default in names:
            user, budget, by_name = await setup_family(session, [(n, "UZS", False) for n in names], default)
            got = await resolve_transfer_wallets(
                session=session, family_budget_id=budget.id, writer=user,
                from_hint=frm, to_hint=to, amount_currency="UZS", default_wallet=by_name[default])
            assert (got.from_wallet.name, got.to_wallet.name) == (src, dst)


FORM_CASES = [
    # an ending ADDED to the name still says the direction (both orders given by the model)
    (UZ_SET, "Kopilkadan", "Kartaga", "Kopilka", "Karta"),
    (UZ_SET, "Kartaga", "Kopilkadan", "Kopilka", "Karta"),
    (UZ_SET, "Yogadan", "Kartaga", "Yoga", "Karta"),
    (UZ_SET, "Kartadan", "Buqaga", "Karta", "Buqa"),
    (UZ_SET, "Saraga", "Kartadan", "Karta", "Sara"),
    # a name ending like an ending beside a real ending: the real one decides
    (UZ_SET, "Kopilka", "Kartadan", "Karta", "Kopilka"),
    (UZ_SET, "Kartaga", "Kopilka", "Kopilka", "Karta"),
    # Latin spelling of a Russian name
    (RU_SET, "kopilkadan", "kartaga", "Копилка", "Карта"),
    (RU_SET, "kartaga", "kopilkadan", "Копилка", "Карта"),
    (RU_SET, "с копилки", "на карту", "Копилка", "Карта"),
    (RU_SET, "Копилка", "Карта", "Копилка", "Карта"),
    (RU_SET, "Наличка", "Карта", "Наличка", "Карта"),
]


@pytest.mark.parametrize("names,frm,to,exp_from,exp_to", FORM_CASES)
async def test_added_endings_decide_direction(names, frm, to, exp_from, exp_to) -> None:
    async with rollback_session() as session:
        for default in names:
            user, budget, by_name = await setup_family(session, [(n, "UZS", False) for n in names], default)
            got = await resolve_transfer_wallets(
                session=session, family_budget_id=budget.id, writer=user,
                from_hint=frm, to_hint=to, amount_currency="UZS", default_wallet=by_name[default])
            assert (got.from_wallet.name, got.to_wallet.name) == (exp_from, exp_to)


async def test_transfer_through_the_handler_keeps_plain_names_order(monkeypatch) -> None:
    for lang, (src, dst) in (("ru", ("Копилка", "Карта")), ("ru", ("Наличка", "Карта")),
                             ("uz", ("Kopilka", "Karta"))):
        async with rollback_session() as session:
            user, budget, by_name = await setup_family(
                session, [(n, "UZS", False) for n in (src, dst)], dst, language=lang)
            set_parser_override(FixedParser(ParsedOperation(
                type="transfer", amount=50000, currency="UZS", wallet_hint=None, category=None,
                comment=None, from_wallet_hint=src, to_wallet_hint=dst)))
            import bot.quick_entry.handlers as h
            monkeypatch.setattr(h, "async_session_factory", SessionFactory(session))
            await handle_quick_entry_text(_message(user.telegram_id, "perevod 50000"), SimpleNamespace())
            txn = (await session.scalars(select(Transaction).where(
                Transaction.family_budget_id == budget.id, Transaction.type == "transfer"))).one()
            assert (txn.wallet_id, txn.to_wallet_id) == (by_name[src].id, by_name[dst].id)


# ---- 2: two cards named alike, bare amount: the usual currency decides on the quick path
async def test_quick_path_two_equal_cards_bare_amount(monkeypatch) -> None:
    async with rollback_session() as session:
        user, budget, by_name = await setup_family(session, [("Наличные", "UZS", False)], "Наличные")
        uzs = Wallet(family_budget_id=budget.id, name="Карта", currency="UZS", is_personal=False)
        usd = Wallet(family_budget_id=budget.id, name="Карта", currency="USD", is_personal=False)
        session.add_all([uzs, usd])
        await session.flush()
        await _add_taxi(session, budget)
        set_parser_override(FailingParser())
        import bot.quick_entry.handlers as h
        monkeypatch.setattr(h, "async_session_factory", SessionFactory(session))
        await handle_quick_entry_text(_message(user.telegram_id, "такси 20000 Карта"), SimpleNamespace())
        txn = (await session.scalars(select(Transaction).where(
            Transaction.family_budget_id == budget.id))).one()
        assert txn.wallet_id == uzs.id
        await handle_quick_entry_text(_message(user.telegram_id, "такси 20 usd Карта"), SimpleNamespace())
        txn = (await session.scalars(select(Transaction).where(
            Transaction.family_budget_id == budget.id, Transaction.amount == 20))).one()
        assert txn.wallet_id == usd.id


# ---- 3 and 5: what is a wallet mention; the same on both paths
CASH_CARD = [("Наличный сум", "UZS", False), ("Карта сум", "UZS", False)]
SHORT = [("Карта", "UZS", False), ("Нал", "UZS", False)]
KOP = [("Карта", "UZS", False), ("Копилка", "UZS", False)]
LATIN = [("Naqd", "UZS", False), ("Karta", "UZS", False)]

# text, wallets, default, wallet expected, words the comment must still have
CASES = [
    # lookalike words are things, not the wallet
    ("такси картошка 20000", CASH_CARD, "Наличный сум", "Наличный сум", ["картошка"]),
    ("такси 20000 картина", CASH_CARD, "Наличный сум", "Наличный сум", ["картина"]),
    ("наличники такси 20000", CASH_CARD, "Карта сум", "Карта сум", ["наличники"]),
    ("такси 20000 карточка", CASH_CARD, "Наличный сум", "Наличный сум", ["карточка"]),
    ("налог такси 20000", SHORT, "Карта", "Карта", ["налог"]),
    ("такси 20000 налог", SHORT, "Карта", "Карта", ["налог"]),
    # the card as a thing bought: inside the phrase, no preposition, nothing after the amount
    ("такси пополнил карту такси 30000", CASH_CARD, "Наличный сум", "Наличный сум", ["пополнил", "карту"]),
    ("такси карту метро 30000", CASH_CARD, "Наличный сум", "Наличный сум", ["карту", "метро"]),
    ("пополнил карту метро 30000", CASH_CARD, "Наличный сум", "Наличный сум", ["пополнил", "карту"]),
    # the card as a wallet: preposition, instrumental, end of the phrase, right after the amount
    ("такси с карты 20000", CASH_CARD, "Наличный сум", "Карта сум", []),
    ("такси картой 20000", CASH_CARD, "Наличный сум", "Карта сум", []),
    ("такси 20000 карту", CASH_CARD, "Наличный сум", "Карта сум", []),
    ("такси 20000 карту метро", CASH_CARD, "Наличный сум", "Карта сум", ["метро"]),
    ("такси карта 20000", CASH_CARD, "Наличный сум", "Карта сум", []),
    ("такси на карту метро 20000", CASH_CARD, "Наличный сум", "Карта сум", ["метро"]),
    # short name, Latin spellings of Russian names
    ("такси 20000 налом", SHORT, "Карта", "Нал", []),
    ("такси налом 20000", SHORT, "Карта", "Нал", []),
    ("taksi 20000 kopilkadan", KOP, "Карта", "Копилка", []),
    ("kopilkadan taksi 20000", KOP, "Карта", "Копилка", []),
    ("такси 20000 копилкой", KOP, "Карта", "Копилка", []),
    ("taksi 20000 kartadan", LATIN, "Naqd", "Karta", []),
]


def _ids(v):
    return v if isinstance(v, str) and len(v) < 40 else None


# phrases the quick path hands over to the model by itself (a "с/на ..." wallet is a transfer sign)
AI_ONLY = {"такси с карты 20000", "такси на карту метро 20000", "пополнил карту метро 30000"}
QUICK_CASES = [c for c in CASES if c[0] not in AI_ONLY]


@pytest.mark.parametrize("text,wallets,default,expected,kept", QUICK_CASES)
async def test_quick_path_rule(monkeypatch, text, wallets, default, expected, kept) -> None:
    name, comment = await _send(monkeypatch, wallets, default, text)
    assert name == expected
    for word in kept:
        assert word in (comment or "").casefold()
    if not kept and expected != default:
        assert (comment or "") == ""


@pytest.mark.parametrize("text,wallets,default,expected,kept", CASES)
async def test_ai_path_gives_the_same_answer(monkeypatch, text, wallets, default, expected, kept) -> None:
    # the model answers with the plain name of the wallet it thinks of, whatever the phrase says
    if expected != default:
        plain = expected
    else:  # a model that takes the lookalike word for a wallet
        plain = next(n for n, _, _ in wallets if n != default)
    op = ParsedOperation(type="expense", amount=20000, currency=None, wallet_hint=plain,
                         category="Такси", comment=text)
    name, comment = await _send(monkeypatch, wallets, default, "поехал " + text, FixedParser(op))
    assert name == expected
    for word in kept:
        assert word in (comment or "").casefold()
