"""ux-next6 L3: parsing a 4096-char text with many numbers is not quadratic (<= 100 ms)."""

import time

import pytest

from app.parsing import prefilter as P
from bot.quick_entry.shopping_pending import bare_text_amount, is_malformed_number

CATS = [
    P.PrefilterCategory(id=i, name=n, translation_key=None, parent_id=None)
    for i, n in enumerate(["Такси", "Продукты", "Кафе", "Зарплата"])
]
N = 4096
TEXTS = {
    "dollars_then_letter": ("$" * (N - 10)) + "a 20000",
    "dollar_punct": ("$!" * N)[: N - 10] + "a 20000",
    "mark_amounts": ("$ ! 1 " * N)[:N],
    "many_numbers": ("1 " * N)[:N],
    "numbers_commas": ("12, 34 " * N)[:N],
    "mag_words": ("5 тыс " * N)[:N],
    "usd_numbers": ("usd 5 " * N)[:N],
    "spaced_k": ("1 к " * N)[:N] + "врачу",
}


@pytest.mark.parametrize("name", sorted(TEXTS))
def test_long_text_parse_is_fast(name: str) -> None:
    text = TEXTS[name]
    t0 = time.perf_counter()
    P.try_prefilter(
        text, wallet_names=["Карта", "Наличные"], expense_categories=CATS[:3],
        income_categories=CATS[3:], seed_name_by_key={},
    )
    bare_text_amount(text)
    is_malformed_number(text)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert elapsed_ms <= 100, f"{name}: {elapsed_ms:.0f} ms"
