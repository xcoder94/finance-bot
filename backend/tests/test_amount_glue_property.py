"""Fast path never keeps only the first of two glued/mis-grouped numbers."""

import random

import pytest

from app.parsing.prefilter import PrefilterCategory, try_prefilter

_CATS = [PrefilterCategory(id=1, name="Такси", translation_key=None, parent_id=None)]

_GROUP = [" ", "_", "\t", " ", " "]
# every multiplier look-alike in both cases, glued and spaced, plus the QA separator list
_MULTS = ["x", "х", "X", "Х", "×", "✕", "✖", "*", "·"]
_SEPS = (
    _GROUP
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
        legit = len(a) <= 3 and len(b) == 3 and sep in _GROUP
        if not (legit and op.amount == int(a + b)):
            bad.append((text, op.amount))
    assert not bad, bad[:10]


@pytest.mark.parametrize("mult", _MULTS)
@pytest.mark.parametrize("text", ["такси 20000 {}2", "20000{}2", "ТАКСИ 20000 {}2", "{}2 20000 такси", "2{}20000 такси", "2 {} 20000 такси"])
def test_every_multiplier_symbol_and_case_goes_to_model(mult: str, text: str) -> None:
    assert _run(text.format(mult)) is None
