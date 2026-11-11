"""ux-r11: Uzbek names of the older category set (pharmacy, celebrations, shopping_leisure).

What a Uzbek reader sees for an existing (older) budget's categories, in the bot/API name
and in the change history line.
"""

import pytest

from app.services.change_log_format import DEFAULT_ENTITY_UZ, render_change_payload
from app.services.display_name import SEED_NAMES_UZ, build_seed_name_by_key, display_name

EXPECTED = {
    "pharmacy": "Dorixona",
    "events_celebrations": "To'y va tadbirlar",
    "toi_celebrations": "To'y va marosimlar",
    "shopping_leisure": "Shaxsiy va dam olish",
}


@pytest.mark.parametrize("key,uz", sorted(EXPECTED.items()))
def test_uz_reader_sees_the_uzbek_name_of_an_older_budget_category(key, uz) -> None:
    ru = build_seed_name_by_key()[key]
    assert display_name(ru, key, language="uz") == uz
    assert display_name(ru, key, language="ru") == ru
    assert display_name("Моя своя", key, language="uz") == "Моя своя"  # renamed: person's own name


@pytest.mark.parametrize("key,uz", sorted(EXPECTED.items()))
def test_change_history_line_in_uzbek_uses_the_same_name(key, uz) -> None:
    ru = build_seed_name_by_key()[key]
    payload = {
        "kind": "changed", "on": "2026-03-09", "actor": {"id": None, "name": "Ann"},
        "field": "category", "old": {"name": ru, "tk": key}, "new": {"name": "Иное", "tk": None},
    }
    assert render_change_payload(payload, "uz").endswith(f"toifa {uz} → Иное")


def test_the_two_uzbek_name_tables_agree() -> None:
    for key, value in DEFAULT_ENTITY_UZ.items():
        if key in SEED_NAMES_UZ:
            assert SEED_NAMES_UZ[key] == value, key
