"""ux-next6 L1: a currency mark detached from the number is never ignored silently."""

import pytest

from app.parsing import prefilter as P

CATS = [
    P.PrefilterCategory(id=i, name=n, translation_key=None, parent_id=None)
    for i, n in enumerate(["Такси", "Продукты", "Кафе", "Зарплата"])
]


def _run(text: str):
    return P.try_prefilter(
        text, wallet_names=["Карта", "Наличные"], expense_categories=CATS[:3],
        income_categories=CATS[3:], seed_name_by_key={},
    )


@pytest.mark.parametrize("text", [
    "$ такси 20", "$ такси 20000", "usd taksi 20", "so'm taksi 20000",
    "такси $ 20 ming", "dollar такси 20", "сум такси 20000", "такси uzs 20000 обед",
])
def test_detached_currency_mark_goes_to_model(text: str) -> None:
    assert _run(text).operation is None


@pytest.mark.parametrize("text", ["такси 20000", "такси 20000 сум", "такси $20", "такси 20 тыс", "сумма такси 20000"])
def test_plain_phrases_stay_fast(text: str) -> None:
    assert _run(text).operation is not None
