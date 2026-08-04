from __future__ import annotations

from typing import Protocol


class SpeechUnavailable(Exception):
    """Speech provider did not return a usable response."""


class SpeechClient(Protocol):
    async def transcribe(self, audio: bytes) -> str:
        """Return transcript text, or empty string if nothing was recognised."""
