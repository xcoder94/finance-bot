"""Single rule for showing a wallet/category name (mirrors frontend getDisplayName).

translation_key is a permanent identity of a seeded entity and is never reset on rename.
An entity counts as "still default" only while its stored name equals the seeded name;
once the user renamed it, their own name is what everybody sees (and what goes to AI prompts),
and seed-only extras (cascade keywords) no longer apply.
"""

from __future__ import annotations

from app.services.budget_seed import (
    SEED_EXPENSE_CATEGORIES,
    SEED_INCOME_CATEGORIES,
    SEED_WALLETS,
)


def build_seed_name_by_key() -> dict[str, str]:
    seed: dict[str, str] = {}
    for name, key in SEED_INCOME_CATEGORIES:
        seed[key] = name
    for parent_name, (parent_key, sub_entries) in SEED_EXPENSE_CATEGORIES.items():
        seed[parent_key] = parent_name
        for sub_name, sub_key in sub_entries:
            seed[sub_key] = sub_name
    for name, _currency, key in SEED_WALLETS:
        seed[key] = name
    return seed


_SEED_NAMES = build_seed_name_by_key()


def is_default_name(
    name: str,
    translation_key: str | None,
    seed_name_by_key: dict[str, str] | None = None,
) -> bool:
    if translation_key is None:
        return False
    seed = (seed_name_by_key or _SEED_NAMES).get(translation_key)
    return seed is not None and name.casefold() == seed.casefold()


def display_name(
    name: str,
    translation_key: str | None,
    seed_name_by_key: dict[str, str] | None = None,
) -> str:
    """Backend has only the seeded (ru) text; a renamed entity always shows its own name."""
    seeds = seed_name_by_key or _SEED_NAMES
    if translation_key is not None and is_default_name(name, translation_key, seeds):
        return seeds[translation_key]
    return name
