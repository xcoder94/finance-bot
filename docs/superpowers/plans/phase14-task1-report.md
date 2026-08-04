# Phase 14 Task 1 Report — SPEECH_* config + Google speech client + factory

## Status

DONE (one minor test-mark deviation documented below)

## TDD evidence

### RED — Step 2 (before implementation)

```
cd backend && ./venv/bin/pytest tests/test_phase14_voice.py -q
```

```
ERROR tests/test_phase14_voice.py
ModuleNotFoundError: No module named 'app.speech'
1 error in 0.17s
```

### GREEN — Step 4 (after implementation)

```
cd backend && ./venv/bin/pytest tests/test_phase14_voice.py -q
```

```
7 passed in 0.12s
```

### Full suite (after Task 1)

```
cd backend && ./venv/bin/pytest -q
```

```
403 passed, 1 warning in 24.16s
```

(396 tests existed before Task 1; +7 new = 403.)

## Commit

- `db8cb2f` — feat(speech): add Google speech-to-text client and SPEECH_* config

## Files changed

| File | Action |
|------|--------|
| `backend/app/config.py` | Added `SPEECH_PROVIDER`, `SPEECH_API_KEY`, `SPEECH_MODEL` after `PARSER_*` block |
| `backend/app/speech/__init__.py` | Created (empty) |
| `backend/app/speech/base.py` | Created — `SpeechUnavailable`, `SpeechClient` Protocol |
| `backend/app/speech/google_client.py` | Created — `GoogleSpeechClient`, `_extract_transcript` |
| `backend/app/speech/factory.py` | Created — `_InactiveSpeechClient`, `get_speech_client()` |
| `backend/tests/test_phase14_voice.py` | Created — 7 Task-1 tests |

## What was implemented

- **Config:** three optional env vars mirroring `PARSER_*`.
- **`GoogleSpeechClient`:** POSTs OGG_OPUS / 48000 Hz / ru-RU to `speech:recognize`; model from constructor (env via factory); base64 audio; strips and joins transcript parts; `""` on empty results; `SpeechUnavailable` on transport/HTTP ≥400/non-JSON/malformed structure.
- **`get_speech_client()`:** returns `GoogleSpeechClient` only when `SPEECH_API_KEY` is set and `(SPEECH_PROVIDER or "").lower() == "google"`; otherwise `_InactiveSpeechClient` raising `SpeechUnavailable`.
- No hard-coded model id strings in source (verified by grep).
- Bot handlers, frontend, and `docs/context/**` untouched.

## Disabled / stubbed / mocked / finish later

None.

## Self-review

- Implementation matches brief interfaces and mirrors `get_parser()` / `PARSER_*` pattern.
- Tests cover: happy path (URL, body, transcript), empty results, HTTP error, factory active/inactive branches, config attributes.
- `GoogleSpeechClient._http` is a long-lived `httpx.AsyncClient` (same lifecycle pattern as `HttpParser`); not closed explicitly — acceptable for factory singleton usage in later tasks.
- `logger` is imported in `google_client.py` per brief but unused — harmless, matches plan snippet.

## Concerns

1. **Test marker deviation:** Brief specifies `@pytest.mark.asyncio`; project has no `pytest-asyncio` and all other async tests use `@pytest.mark.anyio`. Tests were written with `asyncio` first (failed as expected on import), then marker changed to `anyio` for GREEN. Logic unchanged.
2. **`.env` read in sandbox:** Collecting tests that import `app.config` requires read access to repo `.env` (pre-existing); run with normal permissions.

## Next tasks (out of scope here)

- Task 2–3: wire speech client into bot voice handlers.
- Task 4: remaining voice tests in same file.
