from app.config import SPEECH_API_KEY, SPEECH_MODEL, SPEECH_PROVIDER
from app.speech.base import SpeechClient, SpeechUnavailable
from app.speech.google_client import GoogleSpeechClient


class _InactiveSpeechClient:
    async def transcribe(self, audio: bytes) -> str:
        raise SpeechUnavailable(
            "speech is inactive: SPEECH_API_KEY missing or SPEECH_PROVIDER is not google"
        )


def get_speech_client() -> SpeechClient:
    if SPEECH_API_KEY and (SPEECH_PROVIDER or "").lower() == "google":
        return GoogleSpeechClient(
            api_key=SPEECH_API_KEY,
            model=SPEECH_MODEL or "",
        )
    return _InactiveSpeechClient()
