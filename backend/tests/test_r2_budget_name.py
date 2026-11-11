"""ux-p4p5 r2 #4: new budgets get the default name in the owner's language."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


from app.models.family_budget import FamilyBudget, default_budget_name
from bot.onboarding import language_callback


@pytest.mark.anyio
def test_default_budget_name_by_language() -> None:
    assert default_budget_name("ru") == "Семейный бюджет"
    assert default_budget_name("uz") == "Oilaviy byudjet"
    assert default_budget_name(None) == "Семейный бюджет"
    assert len(default_budget_name("uz")) <= 30


@pytest.mark.parametrize(
    ("lang", "expected"), [("ru", "Семейный бюджет"), ("uz", "Oilaviy byudjet")]
)
@pytest.mark.anyio
async def test_onboarding_owner_budget_name_follows_language(lang, expected) -> None:
    added: list[object] = []
    session = SimpleNamespace(add=added.append, flush=AsyncMock())

    class Tx:
        async def __aenter__(self):
            return None

        async def __aexit__(self, *a):
            return None

    session.begin = lambda: Tx()

    class Sess:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *a):
            return None

    message = SimpleNamespace(answer=AsyncMock(), delete=AsyncMock())
    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=123),
        message=message,
        data=f"lang:{lang}",
        answer=AsyncMock(),
    )
    state = SimpleNamespace(
        get_data=AsyncMock(
            return_value={"flow": "owner", "telegram_id": 123, "first_name": "T", "username": "t"}
        ),
        clear=AsyncMock(),
    )
    with (
        patch("bot.onboarding.async_session_factory", return_value=Sess()),
        patch("bot.onboarding.get_active_user_by_telegram_id", new=AsyncMock(return_value=None)),
        patch("bot.onboarding.copy_seed_data", new=AsyncMock()),
        patch("bot.onboarding.assign_default_card_uzs", new=AsyncMock()),
    ):
        await language_callback(callback, state, SimpleNamespace(get_me=AsyncMock()))
    budgets = [o for o in added if isinstance(o, FamilyBudget)]
    assert len(budgets) == 1
    assert budgets[0].name == expected


def test_uz_catalogue_uses_toifa_not_kategoriya() -> None:
    from app.services.bot_texts import CATALOGUE

    bad = [
        k
        for k, v in CATALOGUE.items()
        if isinstance(v, dict) and "kategor" in str(v.get("uz", "")).lower()
    ]
    assert bad == []
