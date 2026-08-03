import json
import logging
from typing import Any

import httpx

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

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 10.0
_MAX_ATTEMPTS = 3


def _parse_operations_payload(data: Any) -> list[ParsedOperation]:
    if not isinstance(data, dict):
        raise ParserMalformed("response is not a JSON object")
    raw_ops = data.get("operations")
    if not isinstance(raw_ops, list):
        raise ParserMalformed("operations must be a list")

    operations: list[ParsedOperation] = []
    for item in raw_ops:
        if not isinstance(item, dict):
            raise ParserMalformed("operation entry must be an object")
        op_type = item.get("type")
        if op_type not in (
            "expense",
            "income",
            "ambiguous",
            "transfer",
            "exchange",
        ):
            raise ParserMalformed(f"invalid operation type: {op_type!r}")

        amount = item.get("amount")
        if amount is not None and not isinstance(amount, int):
            raise ParserMalformed("amount must be integer or null")

        currency = item.get("currency")
        if currency is not None and currency not in ("UZS", "USD"):
            raise ParserMalformed(f"invalid currency: {currency!r}")

        wallet_hint = item.get("wallet_hint")
        if wallet_hint is not None and not isinstance(wallet_hint, str):
            raise ParserMalformed("wallet_hint must be string or null")

        category = item.get("category")
        if category is not None and not isinstance(category, str):
            raise ParserMalformed("category must be string or null")

        comment = item.get("comment")
        if comment is not None and not isinstance(comment, str):
            raise ParserMalformed("comment must be string or null")

        from_wallet_hint = item.get("from_wallet_hint")
        if from_wallet_hint is not None and not isinstance(from_wallet_hint, str):
            raise ParserMalformed("from_wallet_hint must be string or null")

        to_wallet_hint = item.get("to_wallet_hint")
        if to_wallet_hint is not None and not isinstance(to_wallet_hint, str):
            raise ParserMalformed("to_wallet_hint must be string or null")

        rate = item.get("rate")
        if rate is not None and not isinstance(rate, int):
            raise ParserMalformed("rate must be integer or null")

        operations.append(
            ParsedOperation(
                type=op_type,
                amount=amount,
                currency=currency,
                wallet_hint=wallet_hint,
                category=category,
                comment=comment,
                from_wallet_hint=from_wallet_hint,
                to_wallet_hint=to_wallet_hint,
                rate=rate,
            )
        )
    return operations


def _extract_text_from_provider_body(provider: str, body: dict[str, Any]) -> str:
    if provider == "openai":
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ParserMalformed("openai response missing choices")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise ParserMalformed("openai response missing message")
        content = message.get("content")
        if not isinstance(content, str):
            raise ParserMalformed("openai response missing content")
        return content

    if provider == "anthropic":
        content_blocks = body.get("content")
        if not isinstance(content_blocks, list) or not content_blocks:
            raise ParserMalformed("anthropic response missing content")
        first = content_blocks[0]
        if not isinstance(first, dict):
            raise ParserMalformed("anthropic content block invalid")
        text = first.get("text")
        if not isinstance(text, str):
            raise ParserMalformed("anthropic response missing text")
        return text

    raise ParserMalformed(f"unsupported parser provider: {provider!r}")


def _should_retry(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


class HttpParser:
    def __init__(
        self,
        provider: str,
        api_key: str,
        model: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._provider = provider
        self._api_key = api_key
        self._model = model
        self._client = client

    async def parse(self, request: ParseRequest) -> ParseResponse:
        if self._provider not in ("openai", "anthropic"):
            raise ParserMalformed(f"unsupported parser provider: {self._provider!r}")
        if not self._model:
            raise ParserMalformed("parser model is not configured")

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=_TIMEOUT_SECONDS)
        try:
            for attempt in range(1, _MAX_ATTEMPTS + 1):
                try:
                    response = await self._post(client, request)
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    logger.warning(
                        "parser network error attempt %s/%s: %s",
                        attempt,
                        _MAX_ATTEMPTS,
                        exc,
                    )
                    if attempt == _MAX_ATTEMPTS:
                        raise ParserUnavailable(str(exc)) from exc
                    continue

                if response.status_code >= 400:
                    if _should_retry(response.status_code):
                        logger.warning(
                            "parser HTTP %s attempt %s/%s",
                            response.status_code,
                            attempt,
                            _MAX_ATTEMPTS,
                        )
                        if attempt == _MAX_ATTEMPTS:
                            raise ParserUnavailable(
                                f"parser HTTP {response.status_code}"
                            )
                        continue
                    raise ParserMalformed(
                        f"parser HTTP {response.status_code}: {response.text}"
                    )

                try:
                    body = response.json()
                except json.JSONDecodeError as exc:
                    raise ParserMalformed("parser response is not JSON") from exc

                try:
                    text_payload = _extract_text_from_provider_body(
                        self._provider, body
                    )
                    payload = json.loads(text_payload)
                    operations = _parse_operations_payload(payload)
                except json.JSONDecodeError as exc:
                    raise ParserMalformed("model content is not JSON") from exc

                return ParseResponse(operations=operations)
        finally:
            if owns_client:
                await client.aclose()

    async def _post(
        self, client: httpx.AsyncClient, request: ParseRequest
    ) -> httpx.Response:
        user_content = build_mutable_parser_payload(request)
        if self._provider == "openai":
            return await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": build_parser_messages(request),
                },
            )

        return await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "max_tokens": 1024,
                "system": IMMUTABLE_PARSER_INSTRUCTIONS,
                "messages": [{"role": "user", "content": user_content}],
            },
        )
