"""Phase 13 — prompt caching (Google explicit cache)."""

from __future__ import annotations

import json
import re

from app.parsing.prompt import (
    IMMUTABLE_PARSER_INSTRUCTIONS,
    build_mutable_parser_payload,
    build_parser_messages,
    prompt_version,
    static_cache_text,
)
from app.parsing.types import ParseRequest


FAMILY_MARKERS = (
    "Карта сум",
    "Наличный сум",
    "такси 25 тысяч",
    "Алишер",
    "2026-08-04",
)


def _sample_request() -> ParseRequest:
    return ParseRequest(
        text="такси 25 тысяч",
        wallet_names=["Карта сум", "Наличный сум"],
        expense_category_names=["Такси", "Еда"],
        income_category_names=["Зарплата"],
    )


def test_static_cache_text_is_stable_and_large_enough():
    a = static_cache_text()
    b = static_cache_text()
    assert a == b
    assert a.startswith(IMMUTABLE_PARSER_INSTRUCTIONS)
    assert len(a) // 4 >= 4096


def test_static_blob_contains_no_family_data():
    static = static_cache_text()
    for marker in FAMILY_MARKERS:
        assert marker not in static
    assert "wallet_names" not in static
    # mutable fields must not appear as substitution slots in static
    assert "{text}" not in static
    assert "{wallet" not in static.lower()


def test_mutable_tail_holds_wallets_message_not_in_static():
    req = _sample_request()
    mutable = build_mutable_parser_payload(req)
    payload = json.loads(mutable)
    assert payload["text"] == "такси 25 тысяч"
    assert payload["wallet_names"] == ["Карта сум", "Наличный сум"]
    assert "такси 25 тысяч" not in static_cache_text()
    assert "Карта сум" not in static_cache_text()


def test_prompt_version_changes_when_static_changes(monkeypatch):
    v1 = prompt_version()
    assert re.fullmatch(r"[0-9a-f]{16}", v1)
    import app.parsing.prompt as prompt_mod

    monkeypatch.setattr(
        prompt_mod,
        "STATIC_CACHE_BALLAST",
        prompt_mod.STATIC_CACHE_BALLAST + "x",
    )
    v2 = prompt_version()
    assert v2 != v1


def test_build_parser_messages_still_system_then_user():
    req = _sample_request()
    messages = build_parser_messages(req)
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == IMMUTABLE_PARSER_INSTRUCTIONS
    assert messages[1]["content"] == build_mutable_parser_payload(req)
