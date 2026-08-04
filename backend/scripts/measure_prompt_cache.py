"""Live Gemini prompt-cache measurement. Exit 2 if credentials missing."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import httpx

from app.config import PARSER_API_KEY, PARSER_MODEL, PARSER_PROVIDER
from app.parsing.google_cache import GooglePromptCache
from app.parsing.prompt import build_mutable_parser_payload
from app.parsing.types import ParseRequest

_BLOCKED_MSG = "blocked: PARSER_* credentials not available"


def _credentials_missing() -> bool:
    return not PARSER_PROVIDER or not PARSER_API_KEY or not PARSER_MODEL


def _sample_request() -> ParseRequest:
    return ParseRequest(
        text="такси 25 тысяч",
        wallet_names=["Карта сум", "Наличный сум"],
        expense_category_names=["Такси", "Еда"],
        income_category_names=["Зарплата"],
    )


async def _measure() -> int:
    cache = GooglePromptCache(api_key=PARSER_API_KEY, model=PARSER_MODEL)
    cache_name = await cache.ensure_cache()
    if not cache_name:
        print("ensure_cache failed", file=sys.stderr)
        return 1

    request = _sample_request()
    user_content = build_mutable_parser_payload(request)
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{PARSER_MODEL}:generateContent"
    )
    body = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_content}],
            }
        ],
        "cachedContent": cache_name,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            params={"key": PARSER_API_KEY},
            headers={"Content-Type": "application/json"},
            json=body,
        )
        response.raise_for_status()
        data = response.json()

    usage = data.get("usageMetadata") or {}
    prompt_count = usage.get("promptTokenCount")
    cached_count = usage.get("cachedContentTokenCount")

    if not isinstance(prompt_count, int) or prompt_count <= 0:
        print("missing or invalid promptTokenCount in response", file=sys.stderr)
        return 1
    if not isinstance(cached_count, int):
        print("missing cachedContentTokenCount in response", file=sys.stderr)
        return 1

    ratio = cached_count / prompt_count
    print(f"promptTokenCount={prompt_count}")
    print(f"cachedContentTokenCount={cached_count}")
    print(f"cached_ratio={ratio:.4f}")

    return 0 if ratio >= 0.90 else 1


def main() -> None:
    if _credentials_missing():
        print(_BLOCKED_MSG)
        raise SystemExit(2)

    if PARSER_PROVIDER != "google":
        print(f"unsupported provider: {PARSER_PROVIDER!r} (google only)")
        raise SystemExit(1)

    raise SystemExit(asyncio.run(_measure()))


if __name__ == "__main__":
    main()
