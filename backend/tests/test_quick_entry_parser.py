import httpx
import pytest
from unittest.mock import patch

from app.parsing.factory import get_parser
from app.parsing.http_adapter import HttpParser
from app.parsing.stub import StubParser
from app.parsing.types import (
    ParseRequest,
    ParseResponse,
    ParsedOperation,
    ParserMalformed,
    ParserUnavailable,
)


@pytest.mark.anyio
async def test_stub_maps_taxi_fixture():
    parser = StubParser()
    response = await parser.parse(
        ParseRequest(
            text="такси 25 тысяч",
            wallet_names=["Карта сум"],
            expense_category_names=["Такси"],
            income_category_names=["Зарплата"],
        )
    )
    assert len(response.operations) == 1
    op = response.operations[0]
    assert op.type == "expense"
    assert op.amount == 25000
    assert op.currency == "UZS"
    assert op.category == "Такси"


@pytest.mark.anyio
async def test_stub_custom_responses_dict():
    custom = ParseResponse(
        operations=[
            ParsedOperation(
                type="income",
                amount=500000,
                currency="UZS",
                wallet_hint=None,
                category="Подарки",
                comment=None,
            )
        ]
    )
    parser = StubParser(responses={"подарили 500 тысяч": custom})
    response = await parser.parse(
        ParseRequest(
            text="подарили 500 тысяч",
            wallet_names=[],
            expense_category_names=[],
            income_category_names=[],
        )
    )
    assert response == custom


@pytest.mark.anyio
async def test_get_parser_inactive_without_api_key():
    with patch("app.parsing.factory.PARSER_API_KEY", None):
        parser = get_parser()
    with pytest.raises(ParserUnavailable):
        await parser.parse(
            ParseRequest(
                text="такси 25 тысяч",
                wallet_names=[],
                expense_category_names=[],
                income_category_names=[],
            )
        )


@pytest.mark.anyio
async def test_http_parser_retries_on_5xx_then_succeeds():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(500, json={"error": "server"})
        body = {
            "choices": [
                {
                    "message": {
                        "content": '{"operations":[{"type":"expense","amount":25000,"currency":"UZS","wallet_hint":null,"category":"Такси","comment":null}]}'
                    }
                }
            ]
        }
        return httpx.Response(200, json=body)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    parser = HttpParser("openai", "test-key", "gpt-4o-mini", client=client)
    response = await parser.parse(
        ParseRequest(
            text="такси 25 тысяч",
            wallet_names=["Карта сум"],
            expense_category_names=["Такси"],
            income_category_names=[],
        )
    )
    assert attempts == 3
    assert response.operations[0].amount == 25000
    await client.aclose()


@pytest.mark.anyio
async def test_http_parser_malformed_4xx_no_retry():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(400, json={"error": "bad request"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    parser = HttpParser("openai", "test-key", "gpt-4o-mini", client=client)
    with pytest.raises(ParserMalformed):
        await parser.parse(
            ParseRequest(
                text="такси 25 тысяч",
                wallet_names=[],
                expense_category_names=[],
                income_category_names=[],
            )
        )
    assert attempts == 1
    await client.aclose()


@pytest.mark.anyio
async def test_http_parser_unavailable_after_retry_exhausted():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, json={"error": "unavailable"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    parser = HttpParser("openai", "test-key", "gpt-4o-mini", client=client)
    with pytest.raises(ParserUnavailable):
        await parser.parse(
            ParseRequest(
                text="такси 25 тысяч",
                wallet_names=[],
                expense_category_names=[],
                income_category_names=[],
            )
        )
    assert attempts == 3
    await client.aclose()
