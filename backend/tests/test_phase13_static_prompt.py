"""Phase 13 — static parsing prompt, sent in full on every call.

Explicit Google context caching was removed: storage is billed per
token-hour and cost far more than the token discount it bought at our
volume. Nothing here may reintroduce a `cachedContent` reference.
"""

from __future__ import annotations

import json
import socket
from datetime import UTC, datetime

import httpx
import pytest

from app.parsing.http_adapter import HttpParser
from app.parsing.prompt import (
    IMMUTABLE_PARSER_INSTRUCTIONS,
    build_mutable_parser_payload,
    build_parser_messages,
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


def test_static_instructions_are_stable_and_carry_no_ballast():
    static = IMMUTABLE_PARSER_INSTRUCTIONS
    assert static == IMMUTABLE_PARSER_INSTRUCTIONS
    assert "ballast" not in static.lower()
    assert len(static) < 8000


def test_static_blob_contains_no_family_data():
    static = IMMUTABLE_PARSER_INSTRUCTIONS
    for marker in FAMILY_MARKERS:
        assert marker not in static
    assert "wallet_names" not in static
    assert "{text}" not in static
    assert "{wallet" not in static.lower()


def test_mutable_tail_holds_wallets_message_not_in_static():
    req = _sample_request()
    payload = json.loads(build_mutable_parser_payload(req))
    assert payload["text"] == "такси 25 тысяч"
    assert payload["wallet_names"] == ["Карта сум", "Наличный сум"]
    assert "такси 25 тысяч" not in IMMUTABLE_PARSER_INSTRUCTIONS
    assert "Карта сум" not in IMMUTABLE_PARSER_INSTRUCTIONS


def test_build_parser_messages_still_system_then_user():
    req = _sample_request()
    messages = build_parser_messages(req)
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == IMMUTABLE_PARSER_INSTRUCTIONS
    assert messages[1]["content"] == build_mutable_parser_payload(req)


def test_no_cache_module_remains():
    with pytest.raises(ModuleNotFoundError):
        __import__("app.parsing.google_cache")


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


_OPS_JSON = (
    '{"operations":[{"type":"expense","amount":25000,"currency":"UZS",'
    '"wallet_hint":null,"category":"Такси","comment":null,'
    '"from_wallet_hint":null,"to_wallet_hint":null,"rate":null}]}'
)


@pytest.mark.anyio
async def test_google_full_prompt_parse_succeeds():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json=_google_ok_body(_OPS_JSON))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    parser = HttpParser("google", "test-key", "test-model-from-env", client=client)
    response = await parser.parse(_sample_request())
    assert response.operations[0].amount == 25000
    assert "generateContent" in seen["url"]
    assert "test-model-from-env" in seen["url"]
    assert "test-key" not in seen["url"]
    assert "cachedContent" not in seen["body"]
    assert seen["body"]["systemInstruction"]["parts"][0]["text"] == (
        IMMUTABLE_PARSER_INSTRUCTIONS
    )
    assert json.loads(seen["body"]["contents"][0]["parts"][0]["text"])["text"] == (
        "такси 25 тысяч"
    )
    await client.aclose()


@pytest.mark.anyio
async def test_no_call_ever_touches_cachedcontents_endpoint():
    """Text, audio and image turns alike: no cache endpoint, no cachedContent."""
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        body = json.loads(request.content.decode())
        assert "cachedContent" not in body
        return httpx.Response(200, json=_google_ok_body(_OPS_JSON))

    requests = [
        _sample_request(),
        ParseRequest(
            text=None,
            wallet_names=[],
            expense_category_names=[],
            income_category_names=[],
            audio_base64="AAAA",
            audio_mime_type="audio/ogg",
        ),
        ParseRequest(
            text=None,
            wallet_names=[],
            expense_category_names=[],
            income_category_names=[],
            image_base64="AAAA",
            image_mime_type="image/jpeg",
        ),
    ]

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    parser = HttpParser("google", "test-key", "test-model", client=client)
    for req in requests:
        await parser.parse(req)
    assert paths
    assert all("cachedContents" not in path for path in paths)
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


@pytest.mark.anyio
async def test_google_api_key_sent_as_header_not_url_query():
    """Regression: httpx logs the full request URL at INFO level. The API
    key must never appear there — it belongs in the x-goog-api-key header.
    """
    api_key = "AQ.Ab8RN6-super-secret-value"
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        return httpx.Response(200, json=_google_ok_body(_OPS_JSON))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    parser = HttpParser("google", api_key, "test-model", client=client)
    await parser.parse(_sample_request())

    assert api_key not in seen["url"]
    assert seen["headers"]["x-goog-api-key"] == api_key
