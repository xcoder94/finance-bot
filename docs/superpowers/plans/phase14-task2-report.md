# Phase 14 Task 2 — Extract `process_quick_entry_text`

## Status

DONE

## Commit

- `3c886f1` — refactor(quick-entry): extract process_quick_entry_text for voice reuse

## Tests before change

```bash
cd backend && ./venv/bin/pytest tests/test_phase14_voice.py::test_process_quick_entry_text_is_importable -q
```

Result: **FAIL** — `ImportError: cannot import name 'process_quick_entry_text'`

## Tests after change

```bash
cd backend && ./venv/bin/pytest tests/test_phase14_voice.py::test_process_quick_entry_text_is_importable tests/test_quick_entry_flow.py -q
```

Result: **PASS** — 13 passed in 3.72s

## Changes

- `backend/bot/quick_entry/handlers.py` — extracted `process_quick_entry_text(message, bot, text)` with the full parse/create/card pipeline; `handle_quick_entry_text` now strips `message.text` and delegates.
- `backend/tests/test_phase14_voice.py` — appended `test_process_quick_entry_text_is_importable`.

## Disabled / stubbed / mocked

None.

## Notes

- Counter semantics, card wording, and router registration unchanged.
- `len(text) > MAX_MESSAGE_LEN` remains inside the shared core; strip/empty checks stay in the text wrapper only.
- Voice handler not added (Task 3).
