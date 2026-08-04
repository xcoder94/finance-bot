"""Phase 13 — prompt caching (Google explicit cache)."""

from __future__ import annotations

import asyncio
import json
import re
import socket
from datetime import UTC, datetime

import httpx
import pytest

from app.parsing.google_cache import (
    CACHE_DISPLAY_PREFIX,
    GooglePromptCache,
    cache_display_name,
)
from app.parsing.http_adapter import HttpParser
from app.parsing.prompt import (
    IMMUTABLE_PARSER_INSTRUCTIONS,
    build_mutable_parser_payload,
    build_parser_messages,
    prompt_version,
    static_cache_text,
)
from app.parsing.stub import StubParser
from app.parsing.types import ParseRequest, ParserMalformed
from app.services.quick_entry_create import create_quick_entry_expense, resolve_category_id
from tests.test_quick_entry_create import create_user, rollback_session, seed_expense_tree


def _db_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            return True
    except OSError:
        return False


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
async def test_ensure_cache_creates_with_static_only():
    calls: list[tuple[str, str, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode()) if request.content else None
        calls.append((request.method, str(request.url), body))
        if request.method == "GET" and request.url.path.endswith("/cachedContents"):
            return httpx.Response(200, json={"cachedContents": []})
        if request.method == "POST" and request.url.path.endswith("/cachedContents"):
            assert body["systemInstruction"]["parts"][0]["text"] == static_cache_text()
            assert body["displayName"] == cache_display_name(prompt_version())
            assert body["model"] == "models/test-model-from-env"
            for marker in FAMILY_MARKERS:
                assert marker not in json.dumps(body, ensure_ascii=False)
            return httpx.Response(
                200,
                json={
                    "name": "cachedContents/abc123",
                    "displayName": body["displayName"],
                    "expireTime": "2099-01-01T00:00:00Z",
                },
            )
        return httpx.Response(500, json={"error": "unexpected"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    cache = GooglePromptCache("test-key", "test-model-from-env", client=client)
    name = await cache.ensure_cache()
    assert name == "cachedContents/abc123"
    assert cache.get_cached_name() == name
    await client.aclose()


@pytest.mark.anyio
async def test_prompt_version_change_deletes_old_cache():
    deleted: list[str] = []
    post_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal post_count
        if request.method == "GET" and request.url.path.endswith("/cachedContents"):
            return httpx.Response(
                200,
                json={
                    "cachedContents": [
                        {
                            "name": "cachedContents/old1",
                            "displayName": f"{CACHE_DISPLAY_PREFIX}deadbeefdeadbeef",
                        }
                    ]
                },
            )
        if request.method == "DELETE":
            deleted.append(str(request.url.path))
            return httpx.Response(200, json={})
        if request.method == "POST" and request.url.path.endswith("/cachedContents"):
            post_count += 1
            return httpx.Response(
                200,
                json={
                    "name": "cachedContents/new1",
                    "displayName": cache_display_name(prompt_version()),
                },
            )
        return httpx.Response(500, json={"error": "unexpected"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    cache = GooglePromptCache("test-key", "test-model-from-env", client=client)
    name = await cache.ensure_cache()
    assert name == "cachedContents/new1"
    assert post_count == 1
    assert any("cachedContents/old1" in d for d in deleted)
    await client.aclose()


@pytest.mark.anyio
async def test_ensure_cache_reuses_matching_display_name():
    post_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal post_count
        if request.method == "GET" and request.url.path.endswith("/cachedContents"):
            return httpx.Response(
                200,
                json={
                    "cachedContents": [
                        {
                            "name": "cachedContents/existing",
                            "displayName": cache_display_name(prompt_version()),
                        }
                    ]
                },
            )
        if request.method == "POST" and request.url.path.endswith("/cachedContents"):
            post_count += 1
            return httpx.Response(200, json={"name": "cachedContents/new"})
        return httpx.Response(500, json={"error": "unexpected"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    cache = GooglePromptCache("test-key", "test-model-from-env", client=client)
    name = await cache.ensure_cache()
    assert name == "cachedContents/existing"
    assert post_count == 0
    await client.aclose()


@pytest.mark.anyio
async def test_ensure_cache_returns_none_on_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "down"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    cache = GooglePromptCache("test-key", "test-model-from-env", client=client)
    assert await cache.ensure_cache() is None
    assert cache.get_cached_name() is None
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


@pytest.mark.anyio
async def test_missing_cache_still_parses_and_schedules_rebuild():
    """Cache miss must not fail parse; rebuild scheduled in background."""
    rebuild_calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path.endswith("/cachedContents"):
            return httpx.Response(200, json={"cachedContents": []})
        if request.method == "POST" and path.endswith("/cachedContents"):
            rebuild_calls.append("create")
            return httpx.Response(
                200,
                json={
                    "name": "cachedContents/rebuilt",
                    "displayName": cache_display_name(prompt_version()),
                },
            )
        if "generateContent" in path:
            body = json.loads(request.content.decode())
            assert "cachedContent" not in body
            assert body["systemInstruction"]["parts"][0]["text"] == static_cache_text()
            ops = (
                '{"operations":[{"type":"expense","amount":25000,"currency":"UZS",'
                '"wallet_hint":null,"category":"Такси","comment":null,'
                '"from_wallet_hint":null,"to_wallet_hint":null,"rate":null}]}'
            )
            return httpx.Response(200, json=_google_ok_body(ops))
        return httpx.Response(500, json={"error": "unexpected"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    cache = GooglePromptCache("test-key", "test-model-from-env", client=client)
    cache.clear_local()
    parser = HttpParser(
        "google",
        "test-key",
        "test-model-from-env",
        client=client,
        prompt_cache=cache,
    )
    response = await parser.parse(_sample_request())
    assert response.operations[0].amount == 25000
    await asyncio.sleep(0.05)
    assert "create" in rebuild_calls
    await client.aclose()


@pytest.mark.anyio
async def test_cached_parse_references_cache_not_static():
    def handler(request: httpx.Request) -> httpx.Response:
        if "generateContent" in request.url.path:
            body = json.loads(request.content.decode())
            assert body.get("cachedContent") == "cachedContents/abc"
            assert "systemInstruction" not in body
            ops = (
                '{"operations":[{"type":"expense","amount":1000,"currency":"UZS",'
                '"wallet_hint":null,"category":null,"comment":null,'
                '"from_wallet_hint":null,"to_wallet_hint":null,"rate":null}]}'
            )
            return httpx.Response(200, json=_google_ok_body(ops))
        if request.method == "PATCH":
            return httpx.Response(200, json={"name": "cachedContents/abc"})
        return httpx.Response(500, json={"error": "unexpected"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    cache = GooglePromptCache("test-key", "test-model-from-env", client=client)
    cache._local_name = "cachedContents/abc"
    cache._local_version = prompt_version()
    parser = HttpParser(
        "google", "test-key", "test-model-from-env", client=client, prompt_cache=cache
    )
    response = await parser.parse(_sample_request())
    assert response.operations[0].amount == 1000
    await asyncio.sleep(0.05)
    await client.aclose()


@pytest.mark.anyio
@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
async def test_stub_parser_path_still_creates_transaction():
    async with rollback_session() as session:
        user, budget = await create_user(session, telegram_id=1_013_001)
        wallet, _, _, _, _ = await seed_expense_tree(session, budget)
        parser = StubParser()
        parse_response = await parser.parse(_sample_request())
        op = parse_response.operations[0]
        category_id = await resolve_category_id(
            session, budget.id, op_type="expense", category_name=op.category
        )
        txn = await create_quick_entry_expense(
            session,
            user,
            amount=op.amount,
            wallet_id=wallet.id,
            expense_category_id=category_id,
            comment=op.comment,
            transaction_date=datetime(2026, 8, 4, 12, 0, tzinfo=UTC),
        )
        assert txn.amount == 25000
