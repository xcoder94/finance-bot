"""Fast path never keeps only the first of two glued/mis-grouped numbers."""

import random
import re

import pytest

from app.parsing.prefilter import PrefilterCategory, _find_amounts, try_prefilter

_CATS = [PrefilterCategory(id=1, name="Такси", translation_key=None, parent_id=None)]

_GROUP = [" ", "_", "\u00a0", "\u202f", "\u2009"]
# every multiplier look-alike in both cases, glued and spaced, plus the QA separator list
_MULTS = ["x", "х", "X", "Х", "×", "✕", "✖", "*", "·"]
_GLUE = ["по", "шт", "раза", "ta", "dan", "раз", "№", "#", "−", "–", "—", "+", "-", "\t", "\t\t",
         "Ｘ", "ｘ", "ⅹ", "χ", "ҳ", "ˣ"]
_SEPS = (
    _GROUP
    + _GLUE
    + [f" {g}" for g in _GLUE]
    + [f"{g} " for g in _GLUE]
    + ["  ", "__", " _", "_ ", " ", "\n", ".", ",", ". ", ", ", "-", " - ", "/", " / ", ":", ";",
       "+", " + ", "=", "|", "~", "–", "—", "−", "'", "’", "`"]
    + _MULTS
    + [f" {m} " for m in _MULTS]
    + [f" {m}" for m in _MULTS]
    + [f"{m} " for m in _MULTS]
)
_LAYOUTS = ["такси {}", "{} такси", "такси {} сум", "Такси {}", "такси за {}", "такси {} вчера", "ТАКСИ {}"]


def _run(text: str):
    return try_prefilter(
        text, wallet_names=[], expense_categories=_CATS, income_categories=[], seed_name_by_key={}
    ).operation


def test_random_two_numbers_never_first_only() -> None:
    rnd = random.Random(7)
    pick = lambda: str(rnd.choice([rnd.randint(1, 999), rnd.randint(1000, 999999)]))  # noqa: E731
    bad: list[tuple[str, int]] = []
    for _ in range(30_000):
        a, b, sep, lay = pick(), pick(), rnd.choice(_SEPS), rnd.choice(_LAYOUTS)
        text = lay.format(f"{a}{sep}{b}")
        op = _run(text)
        if op is None:
            continue
        legit = len(a) <= 3 and len(b) == 3 and sep in _GROUP  # I2
        if not (legit and op.amount == int(a + b)):
            bad.append((text, op.amount))
        _assert_covered(text, op.amount)  # I1
    assert not bad, bad[:10]


def _assert_covered(text: str, amount: int) -> None:
    """I1: a fast-path hit means every digit char of the text is inside the one amount token."""
    found = _find_amounts(text)
    assert len(found) == 1, text
    start, end = found[0].span
    for m in re.finditer(r"\d", text):
        assert start <= m.start() < end, (text, amount)
    base = int("".join(re.findall(r"\d", text[start:end])))
    assert amount in (base, base * 1000, base * 1_000_000), (text, amount)


_AR = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
_FW = str.maketrans("0123456789", "０１２３４５６７８９")


def test_random_two_numbers_unicode_digits_never_first_only() -> None:
    rnd = random.Random(11)
    bad: list[tuple[str, int]] = []
    for _ in range(10_000):
        a, b = str(rnd.randint(1, 999)), str(rnd.randint(100, 999))
        a = a.translate(rnd.choice([_AR, _FW, {}]))
        b = b.translate(rnd.choice([_AR, _FW, {}]))
        sep, lay = rnd.choice(_SEPS), rnd.choice(_LAYOUTS)
        text = lay.format(f"{a}{sep}{b}")
        op = _run(text)
        if op is None:
            continue
        if not (sep in _GROUP and op.amount == int(a + b)):
            bad.append((text, op.amount))
        _assert_covered(text, op.amount)
    assert not bad, bad[:10]


_OK_BEFORE = set(" \t\n\u00a0\u2009\u202f([«\"',;:")
_OK_AFTER = set(" \t\n\u00a0\u2009\u202f.,;:!?)]»\"'")
_AROUND = (
    list(" \t\n\u00a0\u2009\u202f([«\"',;:.!?)]»")
    + list("-−–—+*×x✕✖·Xхх_/\\=|~#№@%&<>{}^`’abzяшйҳＸｘ")
    + ["\u200b", "\u0301"]
)


def test_single_number_hits_iff_neighbours_whitelisted() -> None:
    """I3: one number with one glued char on each side: hit iff both neighbours are whitelisted."""
    rnd = random.Random(5)
    bad: list[tuple[str, object]] = []
    for _ in range(6_000):
        n = rnd.randint(1, 10**rnd.randint(1, 9))
        before, after = rnd.choice(_AROUND), rnd.choice(_AROUND)
        gap = rnd.choice(["", " "])
        text = f"такси{gap}{before}{n}{after}"
        op = _run(text)
        # a dash glued to the word on its left is a separator (I3 extension, amount5)
        before_ok = before in _OK_BEFORE or (gap == "" and before in "-–—")
        expect = before_ok and after in _OK_AFTER
        if expect != (op is not None) or (op is not None and op.amount != n):
            bad.append((text, None if op is None else op.amount))
    assert not bad, bad[:10]


@pytest.mark.parametrize("mult", _MULTS)
@pytest.mark.parametrize("text", ["такси 20000 {}2", "20000{}2", "ТАКСИ 20000 {}2", "{}2 20000 такси", "2{}20000 такси", "2 {} 20000 такси"])
def test_every_multiplier_symbol_and_case_goes_to_model(mult: str, text: str) -> None:
    assert _run(text.format(mult)) is None


@pytest.mark.parametrize(
    "text,amount,comment",
    [
        ("такси 20000 к врачу", 20_000, "к врачу"),
        ("такси 15000 к работе", 15_000, "к работе"),
        ("такси 20 к", 20_000, None),
        ("такси 20к", 20_000, None),
        ("такси 20 k.", 20_000, None),
    ],
)
def test_spaced_k_is_preposition_only_before_a_word(text: str, amount: int, comment) -> None:
    op = _run(text)
    assert op is not None and op.amount == amount and op.comment == comment


_CUR_WORDS = ["usd", "USD", "Usd", "доллар", "долларов", "доллара", "dollar", "dollarlar", "долл", "долл.", "$", "uzs", "сум"]


def test_currency_word_before_number_goes_to_model() -> None:
    """I4 mirrored: a currency word/sign left of the number that is not in the sum -> model."""
    rnd = random.Random(9)
    bad = []
    for _ in range(4_000):
        w, n = rnd.choice(_CUR_WORDS), rnd.randint(1, 999_999)
        tail = rnd.choice(["", " тыс", " млн", "к", " сум", " usd", "."])
        gap = rnd.choice([" ", "  ", " "])
        text = rnd.choice(["такси {w}{g}{n}{t}", "{w}{g}{n}{t} такси"]).format(w=w, g=gap, n=n, t=tail)
        if _run(text) is not None:
            bad.append(text)
    assert not bad, bad[:10]


@pytest.mark.parametrize("w", ["сумма", "сумка", "usdt", "ксум"])
def test_word_that_only_starts_like_a_currency_is_not_a_mark(w: str) -> None:
    op = _run(f"такси {w} 20000")
    assert op is not None and op.amount == 20_000


def test_spaced_k_plus_word_below_1000_never_saved() -> None:
    """Fast path never saves N<1000 when " к "/" k " + word follows N (ambiguous -> model)."""
    rnd = random.Random(13)
    bad = []
    for _ in range(5_000):
        n = rnd.choice([rnd.randint(1, 999), rnd.randint(1000, 999_999)])
        k, w = rnd.choice(["к", "k", "К", "K"]), rnd.choice(["врачу", "такси", "с", "vrachu"])
        gap = rnd.choice([" ", "  ", " "])
        text = f"такси {n}{gap}{k}{gap}{w}"
        op = _run(text)
        if n < 1000 and op is not None:
            bad.append(text)
        if n >= 1000 and (op is None or op.amount != n):
            bad.append(text)
    assert not bad, bad[:10]
