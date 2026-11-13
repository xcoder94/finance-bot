"""Fast path never keeps only the first of two glued/mis-grouped numbers."""

import random

from app.parsing.prefilter import PrefilterCategory, try_prefilter

_CATS = [PrefilterCategory(id=1, name="Такси", translation_key=None, parent_id=None)]


def _run(text: str):
    return try_prefilter(
        text, wallet_names=[], expense_categories=_CATS, income_categories=[], seed_name_by_key={}
    ).operation


def test_random_two_numbers_never_first_only() -> None:
    rnd = random.Random(7)
    pick = lambda: str(rnd.choice([rnd.randint(1, 999), rnd.randint(1000, 999999)]))  # noqa: E731
    seps = [" ", "  ", "_", "__", "_ ", " _", "\t", " ", "x", "х", "*", "×", "x "]
    bad: list[tuple[str, int]] = []
    for _ in range(20_000):
        a, b, sep = pick(), pick(), rnd.choice(seps)
        text = f"такси {a}{sep}{b}"
        op = _run(text)
        if op is None:
            continue
        legit = len(a) <= 3 and len(b) == 3 and sep in (" ", "_", "\t", " ")
        if not (legit and op.amount == int(a + b)):
            bad.append((text, op.amount))
    assert not bad, bad[:10]
