"""ux-next4 (QA round 3, bugs D and E): one wallet rule on the quick path and on the AI path."""
import pytest

from app.parsing.prefilter import PrefilterResult
from app.parsing.types import ParsedOperation
from tests.test_ux_next2_wallets import _send
from tests.test_ux_r15_wallet_pick import FixedParser

pytestmark = pytest.mark.anyio

CC = [("Наличные", "UZS", False), ("Карта", "UZS", False)]
UZ = [("Naqd", "UZS", False), ("Karta", "UZS", False), ("Humo", "UZS", False)]
SHORT = [("Карта", "UZS", False), ("Нал", "UZS", False)]
TWO_CASH = [("Наличные", "UZS", False), ("Нал", "UZS", False), ("Карта", "UZS", False)]
EMO = [("💵 Наличные", "UZS", False), ("💳 Карта", "UZS", False)]

# text, wallets, default, wallet expected, comment expected ("" = nothing left, else words kept)
CASES = [
    # D: Uzbek postpositions after the name, the name first, Russian "через/по" + form
    ("humo bilan taksi 20000", UZ, "Naqd", "Humo", ""),
    ("karta bilan taksi 20000", UZ, "Naqd", "Karta", ""),
    ("humo orqali taksi 20000", UZ, "Naqd", "Humo", ""),
    ("taksi 20000 humo bilan", UZ, "Naqd", "Humo", ""),
    ("taksi humo orqali 20000", UZ, "Naqd", "Humo", ""),
    ("naqd pul bilan taksi 20000", UZ, "Karta", "Naqd", ""),
    ("karta taksi 20000", UZ, "Naqd", "Karta", ""),
    ("карта такси 20000", CC, "Наличные", "Карта", ""),
    ("через карту такси 20000", CC, "Наличные", "Карта", ""),
    ("такси по карте 20000", CC, "Наличные", "Карта", ""),
    # E: Latin short name = the same wallet on both paths; slang for cash
    ("такси 20000 nal", SHORT, "Карта", "Нал", ""),
    ("taksi 20000 naldan", SHORT, "Карта", "Нал", ""),
    ("такси налик 20000", CC, "Карта", "Наличные", ""),
    ("такси 20000 наличкой", CC, "Карта", "Наличные", ""),
    ("такси 20000 наликом", CC, "Карта", "Наличные", ""),
    ("такси 20000 налом", SHORT, "Карта", "Нал", ""),
    # more than one cash wallet: no guessing
    ("такси 20000 наличкой", TWO_CASH, "Карта", "Карта", None),
    # the emoji of the name does not stay in the comment
    ("такси 20000 💳 Карта", EMO, "💵 Наличные", "💳 Карта", ""),
    ("такси 💳 Карта 20000", EMO, "💵 Наличные", "💳 Карта", ""),
]


def _quick_ok(case):
    return case[4] is not None


@pytest.mark.parametrize("text,wallets,default,expected,comment", CASES)
async def test_quick_path(monkeypatch, text, wallets, default, expected, comment) -> None:
    name, got = await _send(monkeypatch, wallets, default, text)
    assert name == expected
    if comment == "":
        assert (got or "") == ""


@pytest.mark.parametrize("text,wallets,default,expected,comment", CASES)
async def test_ai_path_same_answer(monkeypatch, text, wallets, default, expected, comment) -> None:
    if comment is None:
        pytest.skip("two cash wallets: the model's own pick stands on the AI path")
    # the prefilter hands everything to the model; the model names the wallet as written in the list
    monkeypatch.setattr(
        "bot.quick_entry.handlers.try_prefilter",
        lambda *a, **k: PrefilterResult(operation=None, reason="no_category_match"),
    )
    plain = expected if expected != default else next(n for n, _, _ in wallets if n != default)
    op = ParsedOperation(type="expense", amount=20000, currency=None, wallet_hint=plain,
                         category="Такси", comment=text)
    name, got = await _send(monkeypatch, wallets, default, text, FixedParser(op))
    assert name == expected
    if comment == "":
        low = (got or "").casefold()
        for word in ("bilan", "orqali", "💳", "nal", "налик", "наличк", "humo", "karta", "карт"):
            assert word not in low


# things that look like a wallet stay things
THINGS = [
    ("карту метро пополнил 30000", CC, "Наличные"),
    ("карта памяти 50000", CC, "Наличные"),
    ("karta sotib oldim 50000", UZ, "Naqd"),
]


@pytest.mark.parametrize("text,wallets,default", THINGS)
async def test_things_stay_things_on_the_ai_path(monkeypatch, text, wallets, default) -> None:
    monkeypatch.setattr(
        "bot.quick_entry.handlers.try_prefilter",
        lambda *a, **k: PrefilterResult(operation=None, reason="no_category_match"),
    )
    hint = next(n for n, _, _ in wallets if n.lower().startswith(("карта", "karta")))
    op = ParsedOperation(type="expense", amount=30000, currency=None, wallet_hint=hint,
                         category="Такси", comment=text)
    name, got = await _send(monkeypatch, wallets, default, text, FixedParser(op))
    assert name == default
