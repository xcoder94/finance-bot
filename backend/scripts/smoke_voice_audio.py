"""Smoke-test voice parsing via HttpParser. Exit 2 if PARSER_* credentials missing."""

from __future__ import annotations

import asyncio
import base64
import json
import sys
from dataclasses import asdict
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.config import PARSER_API_KEY, PARSER_MODEL, PARSER_PROVIDER
from app.parsing.http_adapter import HttpParser
from app.parsing.types import (
    ParseRequest,
    ParseResponse,
    ParserMalformed,
    ParserUnavailable,
)

_BLOCKED_MSG = "blocked: PARSER_* credentials not available"


def _credentials_missing() -> bool:
    return not PARSER_PROVIDER or not PARSER_API_KEY or not PARSER_MODEL


def _sample_request(audio_base64: str) -> ParseRequest:
    return ParseRequest(
        text="",
        wallet_names=["Карта сум", "Наличный сум"],
        expense_category_names=["Такси", "Еда"],
        income_category_names=["Зарплата"],
        audio_base64=audio_base64,
        audio_mime_type="audio/ogg",
    )


def _format_response(response: ParseResponse) -> str:
    return json.dumps(asdict(response), ensure_ascii=False, indent=2)


async def _run(ogg_path: Path) -> int:
    audio_bytes = ogg_path.read_bytes()
    audio_b64 = base64.b64encode(audio_bytes).decode()
    request = _sample_request(audio_b64)

    parser = HttpParser(
        provider=PARSER_PROVIDER or "",
        api_key=PARSER_API_KEY or "",
        model=PARSER_MODEL or "",
    )

    try:
        response = await parser.parse(request)
    except ParserUnavailable as exc:
        msg = str(exc)
        if "HTTP" in msg:
            print(f"HTTP error: {msg}", file=sys.stderr)
        else:
            print(f"parser unavailable: {msg}", file=sys.stderr)
        return 1
    except ParserMalformed as exc:
        text = str(exc)
        if text.startswith("parser HTTP "):
            print(f"HTTP error: {text}", file=sys.stderr)
        else:
            print(f"parser malformed: {text}", file=sys.stderr)
        return 1

    print(_format_response(response))
    print(f"operations={len(response.operations)}")
    print(f"speech_status={response.speech_status!r}")
    print(f"date_hint={response.date_hint!r}")
    return 0


def main() -> None:
    if _credentials_missing():
        print(_BLOCKED_MSG)
        raise SystemExit(2)

    if len(sys.argv) != 2:
        print(f"usage: {Path(sys.argv[0]).name} <path-to.ogg>", file=sys.stderr)
        raise SystemExit(1)

    ogg_path = Path(sys.argv[1])
    if not ogg_path.is_file():
        print(f"file not found: {ogg_path}", file=sys.stderr)
        raise SystemExit(1)

    raise SystemExit(asyncio.run(_run(ogg_path)))


if __name__ == "__main__":
    main()
