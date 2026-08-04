"""Phase 15 — receipt photo."""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest

from app.config import receipt_photo_enabled
from app.parsing.http_adapter import HttpParser
from app.parsing.prompt import IMMUTABLE_PARSER_INSTRUCTIONS
from app.parsing.types import ParseRequest, ParseResponse, ParserMalformed, ParserUnavailable
from bot.quick_entry.texts import MSG_RECEIPT_UNREADABLE

MSG_RECEIPT_UNREADABLE_EXPECTED = (
    "Не разобрал чек. Сфотографируйте его целиком при хорошем свете или запишите\n"
    "сумму текстом."
)


def test_parse_request_accepts_optional_image_fields():
    req = ParseRequest(
        text="",
        wallet_names=[],
        expense_category_names=[],
        income_category_names=[],
        image_base64="AAAA",
        image_mime_type="image/jpeg",
    )
    assert req.image_base64 == "AAAA"
    assert req.image_mime_type == "image/jpeg"


def test_parse_response_accepts_receipt_status():
    r = ParseResponse(operations=[], receipt_status="unreadable")
    assert r.receipt_status == "unreadable"


def test_msg_receipt_unreadable_exact_prd_text():
    assert MSG_RECEIPT_UNREADABLE == MSG_RECEIPT_UNREADABLE_EXPECTED


def test_instructions_document_receipt_status_and_rules():
    assert "receipt_status" in IMMUTABLE_PARSER_INSTRUCTIONS
    lowered = IMMUTABLE_PARSER_INSTRUCTIONS.lower()
    assert "total" in lowered or "итог" in lowered


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, False),
        ("", False),
        ("0", False),
        ("false", False),
        ("1", True),
        ("true", True),
        ("TRUE", True),
        ("yes", True),
        ("on", True),
    ],
)
def test_receipt_photo_enabled(monkeypatch: pytest.MonkeyPatch, value: str | None, expected: bool):
    monkeypatch.setattr("app.config.RECEIPT_PHOTO_ENABLED", value)
    assert receipt_photo_enabled() is expected


# --- Task 2: HttpParser image part + receipt_status + 20s timeout ---


def _google_receipt_response(receipt_status: str) -> dict:
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "operations": [],
                                    "receipt_status": receipt_status,
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }


@pytest.mark.anyio
async def test_http_parser_google_posts_inline_image_part():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json=_google_receipt_response("ok"))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        parser = HttpParser("google", "key", "env-model", client=client)
        resp = await parser.parse(
            ParseRequest(
                text="",
                wallet_names=[],
                expense_category_names=[],
                income_category_names=[],
                image_base64="QQ==",
                image_mime_type="image/jpeg",
            )
        )
    assert resp.receipt_status == "ok"
    parts = captured["body"]["contents"][0]["parts"]
    image_parts = [p for p in parts if "inlineData" in p]
    assert len(image_parts) == 1
    assert image_parts[0]["inlineData"]["mimeType"] == "image/jpeg"
    assert image_parts[0]["inlineData"]["data"] == "QQ=="


@pytest.mark.anyio
async def test_http_parser_rejects_image_when_not_google():
    parser = HttpParser("openai", "key", "m")
    with pytest.raises(ParserUnavailable):
        await parser.parse(
            ParseRequest(
                text="",
                wallet_names=[],
                expense_category_names=[],
                income_category_names=[],
                image_base64="QQ==",
                image_mime_type="image/jpeg",
            )
        )


@pytest.mark.anyio
async def test_http_parser_parses_receipt_status_unreadable():
    transport = httpx.MockTransport(
        lambda _r: httpx.Response(200, json=_google_receipt_response("unreadable"))
    )
    async with httpx.AsyncClient(transport=transport) as client:
        parser = HttpParser("google", "key", "m", client=client)
        resp = await parser.parse(
            ParseRequest(
                text="",
                wallet_names=[],
                expense_category_names=[],
                income_category_names=[],
                image_base64="QQ==",
                image_mime_type="image/jpeg",
            )
        )
    assert resp.receipt_status == "unreadable"


@pytest.mark.anyio
async def test_http_parser_invalid_receipt_status_raises_malformed():
    transport = httpx.MockTransport(
        lambda _r: httpx.Response(200, json=_google_receipt_response("maybe"))
    )
    async with httpx.AsyncClient(transport=transport) as client:
        parser = HttpParser("google", "key", "m", client=client)
        with pytest.raises(ParserMalformed):
            await parser.parse(
                ParseRequest(
                    text="",
                    wallet_names=[],
                    expense_category_names=[],
                    income_category_names=[],
                    image_base64="QQ==",
                    image_mime_type="image/jpeg",
                )
            )


@pytest.mark.anyio
async def test_http_parser_image_request_uses_20s_timeout():
    captured_timeouts: list[float] = []
    real_async_client = httpx.AsyncClient

    def mock_client_ctor(*args, **kwargs):
        if "timeout" in kwargs:
            captured_timeouts.append(kwargs["timeout"])
        transport = httpx.MockTransport(
            lambda _r: httpx.Response(200, json=_google_receipt_response("ok"))
        )
        return real_async_client(transport=transport, timeout=kwargs.get("timeout", 10))

    with patch("app.parsing.http_adapter.httpx.AsyncClient", side_effect=mock_client_ctor):
        parser = HttpParser("google", "key", "m")
        await parser.parse(
            ParseRequest(
                text="",
                wallet_names=[],
                expense_category_names=[],
                income_category_names=[],
                image_base64="QQ==",
                image_mime_type="image/jpeg",
            )
        )
    assert captured_timeouts == [20.0]
