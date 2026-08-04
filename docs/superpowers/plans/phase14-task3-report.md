# Phase 14 Task 3 — Voice handler, failure texts, acceptance tests

## Status

DONE

## Commit

- `26d0d55` — feat(bot): wire voice messages through shared quick-entry pipeline

## Tests before change

```bash
cd backend && ./venv/bin/pytest tests/test_phase14_voice.py -q
```

Result: **ERROR** — `ImportError: cannot import name 'handle_quick_entry_voice'` / `set_speech_client_override`

## Tests after change

```bash
cd backend && ./venv/bin/pytest tests/test_phase14_voice.py tests/test_quick_entry_flow.py -q
```

Result: **PASS** — 27 passed in 4.17s

## Changes

- `backend/bot/quick_entry/texts.py` — added `MSG_VOICE_NOT_RECOGNIZED` (exact PRD string).
- `backend/bot/quick_entry/handlers.py` — `set_speech_client_override` / `_get_speech_client`; `handle_quick_entry_voice` (typing → download → transcribe → empty transcript → unparsed + section-9 text, else `process_quick_entry_text`); `@router.message(F.voice)` wrapper.
- `backend/tests/test_phase14_voice.py` — six acceptance tests + constant check; reused DB helpers from `test_quick_entry_flow.py`.

## Acceptance coverage

| Test | Asserts |
|------|---------|
| `test_voice_sets_typing_indicator_immediately` | `send_chat_action(typing)` before `message.answer` |
| `test_voice_transcribed_text_reaches_card_path` | Card with amount; `daily_model_calls == 1` |
| `test_voice_noise_returns_section9_text_and_spends_unparsed` | Exact `MSG_VOICE_NOT_RECOGNIZED`; unparsed +1; no model call |
| `test_voice_no_amount_reuses_msg_no_amount` | Exact `MSG_NO_AMOUNT`; unparsed +1 |
| `test_voice_three_operations_spend_one_model_call` | Three cards; `daily_model_calls == 1` |
| `test_voice_reply_never_contains_transcription_string` | `SECRET_TRANSCRIPT` absent from all answer text/markup |
| `test_voice_speech_unavailable_returns_model_fail_without_unparsed` | Exact `MSG_MODEL_FAIL`; unparsed 0; model calls 0 |

## Disabled / stubbed / mocked

None in production code. Tests use `StubSpeech`, `StubParser`, `SessionFactory`, and `AsyncMock` bot/message.

## Notes

- Transcription text is never echoed in bot replies.
- `SpeechUnavailable` and missing `file_path` answer `MSG_MODEL_FAIL` without unparsed spend.
- Recognised-but-unparseable paths reuse shared core (`MSG_NO_AMOUNT`, single model call for multi-op).

## Review fix — typing kwargs assertion

**Commit:** `9d4c2c3` — test(voice): assert typing chat_action kwargs

**Change:** `test_voice_sets_typing_indicator_immediately` now asserts `bot.send_chat_action.assert_awaited_with(chat_id=message.chat.id, action="typing")` in addition to call-order checks. Existing `AsyncMock(side_effect=...)` preserved `await_args`; no restructure needed.

**Tests:**

```bash
cd backend && ./venv/bin/pytest tests/test_phase14_voice.py::TestVoiceAcceptance::test_voice_sets_typing_indicator_immediately -q
# 1 passed in 3.12s

cd backend && ./venv/bin/pytest tests/test_phase14_voice.py -q
# 15 passed in 3.37s
```

## Review fix — SpeechUnavailable acceptance test

**Commit:** `ae8f662` — `test(voice): cover SpeechUnavailable without unparsed spend`

**Change:** Added `test_voice_speech_unavailable_returns_model_fail_without_unparsed` to `TestVoiceAcceptance`. Uses `StubSpeech(exc=SpeechUnavailable("down"))`, asserts `message.answer` with exact `MSG_MODEL_FAIL`, and `daily_unparsed == 0` / `daily_model_calls == 0`.

**Tests:**

```bash
cd backend && ./venv/bin/pytest tests/test_phase14_voice.py -q
# 16 passed in 3.53s
```
