"""Phase 14 — voice input (Google speech → shared quick-entry pipeline)."""

from __future__ import annotations

import base64
import json
from unittest.mock import patch

import httpx
import pytest

from app.speech.base import SpeechUnavailable
from app.speech.factory import get_speech_client
from app.speech.google_client import GoogleSpeechClient


@pytest.mark.anyio
async def test_google_speech_client_posts_ogg_and_returns_transcript() -> None:
    audio = b"fake-ogg-bytes"
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "results": [
                    {"alternatives": [{"transcript": "такси 25 тысяч"}]},
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    client = GoogleSpeechClient(api_key="test-key", model="env-model-name")
    with patch.object(client, "_http", httpx.AsyncClient(transport=transport)):
        text = await client.transcribe(audio)

    assert text == "такси 25 тысяч"
    assert "speech:recognize" in captured["url"]
    assert "key=test-key" in captured["url"]
    body = captured["body"]
    assert body["config"]["encoding"] == "OGG_OPUS"
    assert body["config"]["sampleRateHertz"] == 48000
    assert body["config"]["languageCode"] == "ru-RU"
    assert body["config"]["model"] == "env-model-name"
    assert body["audio"]["content"] == base64.b64encode(audio).decode()


@pytest.mark.anyio
async def test_google_speech_client_empty_results_returns_empty_string() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": []})

    client = GoogleSpeechClient(api_key="k", model="m")
    with patch.object(
        client, "_http", httpx.AsyncClient(transport=httpx.MockTransport(handler))
    ):
        assert await client.transcribe(b"x") == ""


@pytest.mark.anyio
async def test_google_speech_client_http_error_raises_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": {"message": "down"}})

    client = GoogleSpeechClient(api_key="k", model="m")
    with patch.object(
        client, "_http", httpx.AsyncClient(transport=httpx.MockTransport(handler))
    ):
        with pytest.raises(SpeechUnavailable):
            await client.transcribe(b"x")


def test_get_speech_client_inactive_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.speech.factory.SPEECH_API_KEY", None)
    monkeypatch.setattr("app.speech.factory.SPEECH_PROVIDER", None)
    monkeypatch.setattr("app.speech.factory.SPEECH_MODEL", None)
    client = get_speech_client()
    assert client.__class__.__name__ == "_InactiveSpeechClient"


def test_get_speech_client_google_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.speech.factory.SPEECH_API_KEY", "key")
    monkeypatch.setattr("app.speech.factory.SPEECH_PROVIDER", "google")
    monkeypatch.setattr("app.speech.factory.SPEECH_MODEL", "from-env")
    client = get_speech_client()
    assert isinstance(client, GoogleSpeechClient)


def test_get_speech_client_inactive_for_non_google_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.speech.factory.SPEECH_API_KEY", "key")
    monkeypatch.setattr("app.speech.factory.SPEECH_PROVIDER", "other")
    monkeypatch.setattr("app.speech.factory.SPEECH_MODEL", "m")
    client = get_speech_client()
    assert client.__class__.__name__ == "_InactiveSpeechClient"


def test_config_exposes_speech_env_vars() -> None:
    from app import config

    assert hasattr(config, "SPEECH_PROVIDER")
    assert hasattr(config, "SPEECH_API_KEY")
    assert hasattr(config, "SPEECH_MODEL")
