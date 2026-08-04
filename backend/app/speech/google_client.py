from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

from app.speech.base import SpeechUnavailable

logger = logging.getLogger(__name__)

_RECOGNIZE_URL = "https://speech.googleapis.com/v1/speech:recognize"
_TIMEOUT_SECONDS = 30.0


class GoogleSpeechClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._http = httpx.AsyncClient(timeout=_TIMEOUT_SECONDS)

    async def transcribe(self, audio: bytes) -> str:
        params = {"key": self._api_key}
        body: dict[str, Any] = {
            "config": {
                "encoding": "OGG_OPUS",
                "sampleRateHertz": 48000,
                "languageCode": "ru-RU",
                "model": self._model,
            },
            "audio": {"content": base64.b64encode(audio).decode("ascii")},
        }
        try:
            response = await self._http.post(_RECOGNIZE_URL, params=params, json=body)
        except httpx.HTTPError as exc:
            raise SpeechUnavailable("speech transport failed") from exc
        if response.status_code >= 400:
            raise SpeechUnavailable(f"speech HTTP {response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            raise SpeechUnavailable("speech response is not JSON") from exc
        return _extract_transcript(data)


def _extract_transcript(data: Any) -> str:
    if not isinstance(data, dict):
        raise SpeechUnavailable("speech response is not an object")
    results = data.get("results") or []
    if not isinstance(results, list):
        raise SpeechUnavailable("speech results malformed")
    parts: list[str] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        alts = item.get("alternatives") or []
        if not isinstance(alts, list) or not alts:
            continue
        first = alts[0]
        if isinstance(first, dict):
            t = first.get("transcript")
            if isinstance(t, str) and t.strip():
                parts.append(t.strip())
    return " ".join(parts)
