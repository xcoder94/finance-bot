"""Phase 13 — prompt caching (Google explicit cache)."""

from __future__ import annotations

import json
import re

import httpx
import pytest

from app.parsing.http_adapter import HttpParser
from app.parsing.prompt import (
    IMMUTABLE_PARSER_INSTRUCTIONS,
    build_mutable_parser_payload,
    build_parser_messages,
    prompt_version,
    static_cache_text,
)
from app.parsing.types import ParseRequest, ParserMalformed


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


def _google_ok_body(ops_json: str) -> dict:
    return {
        "candidates": [
            {"content": {"parts": [{"text": ops_json}], "role": "model"}}
        ],
        "usageMetadata": {
            "promptTokenCount": 100,
            "candidatesTokenCount": 20,
            "totalTokenCount": 120,
        },
    }


@pytest.mark.anyio
async def test_google_full_prompt_parse_succeeds():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content.decode())
        ops = (
            '{"operations":[{"type":"expense","amount":25000,"currency":"UZS",'
            '"wallet_hint":null,"category":"Такси","comment":null,'
            '"from_wallet_hint":null,"to_wallet_hint":null,"rate":null}]}'
        )
        return httpx.Response(200, json=_google_ok_body(ops))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    parser = HttpParser("google", "test-key", "test-model-from-env", client=client)
    response = await parser.parse(_sample_request())
    assert response.operations[0].amount == 25000
    assert "generateContent" in seen["url"]
    assert "test-model-from-env" in seen["url"]
    assert "key=test-key" in seen["url"]
    assert "cachedContent" not in seen["body"]
    assert seen["body"]["systemInstruction"]["parts"][0]["text"] == static_cache_text()
    assert json.loads(seen["body"]["contents"][0]["parts"][0]["text"])["text"] == (
        "такси 25 тысяч"
    )
    await client.aclose()


@pytest.mark.anyio
async def test_google_unsupported_without_model():
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    )
    parser = HttpParser("google", "test-key", "", client=client)
    with pytest.raises(ParserMalformed):
        await parser.parse(_sample_request())
    await client.aclose()
