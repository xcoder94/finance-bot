import httpx
import pytest
from unittest.mock import patch

from app.parsing.factory import get_parser
from app.parsing.http_adapter import HttpParser
from app.parsing.stub import StubParser
from app.parsing.prompt import (
    IMMUTABLE_PARSER_INSTRUCTIONS,
    build_mutable_parser_payload,
    build_parser_messages,
)
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


def test_parsed_operation_accepts_transfer_fields():
    op = ParsedOperation(
        type="transfer",
        amount=500_000,
        currency="UZS",
        wallet_hint=None,
        category=None,
        comment=None,
        from_wallet_hint="карта",
        to_wallet_hint="наличные",
        rate=None,
    )
    assert op.from_wallet_hint == "карта"
    assert op.to_wallet_hint == "наличные"
    assert op.rate is None


def test_prompt_bare_direction_words_rule():
    lowered = IMMUTABLE_PARSER_INSTRUCTIONS.lower()
    for keyword in (
        "kirim",
        "приход",
        "доход",
        "получил",
        "получила",
        "заработал",
        "заработала",
        "chiqim",
        "расход",
        "потратил",
        "потратила",
        "заплатил",
        "заплатила",
    ):
        assert keyword in lowered
    assert "never default to expense" in lowered


def test_prompt_salary_words_are_income_markers():
    lowered = IMMUTABLE_PARSER_INSTRUCTIONS.lower()
    for keyword in (
        "oylik",
        "oyli",
        "maosh",
        "ish haqi",
        "ойлик",
        "маош",
        "зарплата",
        "зп",
        "аванс",
        "оклад",
    ):
        assert keyword in lowered


def test_prompt_income_category_name_match_rule():
    lowered = IMMUTABLE_PARSER_INSTRUCTIONS.lower()
    assert "income_category_names" in lowered


@pytest.mark.anyio
async def test_stub_bare_kirim_income_no_category():
    parser = StubParser()
    response = await parser.parse(
        ParseRequest(
            text="Kirim 500000 som",
            wallet_names=[],
            expense_category_names=[],
            income_category_names=[],
        )
    )
    assert len(response.operations) == 1
    op = response.operations[0]
    assert op.type == "income"
    assert op.amount == 500_000
    assert op.currency == "UZS"
    assert op.category is None


@pytest.mark.anyio
async def test_stub_bare_kirim_ming_income():
    parser = StubParser()
    response = await parser.parse(
        ParseRequest(
            text="kirim 500 ming",
            wallet_names=[],
            expense_category_names=[],
            income_category_names=[],
        )
    )
    assert len(response.operations) == 1
    assert response.operations[0].type == "income"
    assert response.operations[0].amount == 500_000


@pytest.mark.anyio
async def test_stub_bare_chiqim_expense():
    parser = StubParser()
    response = await parser.parse(
        ParseRequest(
            text="Chiqim 500000 som",
            wallet_names=[],
            expense_category_names=[],
            income_category_names=[],
        )
    )
    assert len(response.operations) == 1
    op = response.operations[0]
    assert op.type == "expense"
    assert op.amount == 500_000
    assert op.currency == "UZS"
    assert op.category is None


@pytest.mark.anyio
async def test_stub_bare_oylik_income():
    parser = StubParser()
    response = await parser.parse(
        ParseRequest(
            text="ойлик 500000",
            wallet_names=[],
            expense_category_names=[],
            income_category_names=[],
        )
    )
    assert len(response.operations) == 1
    op = response.operations[0]
    assert op.type == "income"
    assert op.amount == 500_000


def test_prompt_immutable_then_mutable_order():
    req = ParseRequest(
        text="переложил 500 тысяч с карты на наличные",
        wallet_names=["Карта сум", "Наличный сум"],
        expense_category_names=["Такси"],
        income_category_names=["Зарплата"],
    )
    messages = build_parser_messages(req)
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == IMMUTABLE_PARSER_INSTRUCTIONS
    assert "по курсу" in IMMUTABLE_PARSER_INSTRUCTIONS
    assert "transfer" in IMMUTABLE_PARSER_INSTRUCTIONS
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == build_mutable_parser_payload(req)
    assert "переложил 500 тысяч" in messages[1]["content"]
