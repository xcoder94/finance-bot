# Report — Phase 16d: durable error logging for bot and API

Branch: `mvp2/phase-16-cascade-demo-protected-support` (continued; no new branch)  
Date: 2026-08-05  
Orchestrator: Cursor Grok 4.5  
Workers: `composer-2.5` only

---

## Tests

| Moment | Backend (`pytest -q`) | Frontend (`npx vitest run`) |
|--------|------------------------|-----------------------------|
| Baseline (before changes) | **499 passed**, 1 warning | **39 files / 235 passed** |
| Final (after changes) | **502 passed**, 1 warning | **39 files / 235 passed** |

Delta: **+3** backend tests (logging / parser-failure logging). Frontend unchanged.

Disabled / stubbed / mocked: **none**.

---

## What shipped

### Task 1 — shared rotating file logging

- New `backend/app/logging_setup.py` with idempotent `setup_logging()`.
- Console + `RotatingFileHandler` (`maxBytes=5_000_000`, `backupCount=5`).
- Format: `%(asctime)s %(levelname)s %(name)s %(message)s`.
- Path: `LOG_FILE_PATH` env var; default `backend/logs/app.log` (via `_BACKEND_ROOT` in `app/config.py`).
- Wired at startup in `backend/bot/main.py` and `backend/app/main.py` (replaces `logging.basicConfig` in the bot).
- Root `.gitignore` includes `logs/` — `backend/logs/app.log` is ignored (`git check-ignore` confirms).

### Task 2 — parser failure logging

All real `except (ParserUnavailable, ParserMalformed)` sites now call `logger.exception(...)` **before** `MSG_MODEL_FAIL`. User-facing behaviour unchanged.

| Site | File | `entry_path` |
|------|------|--------------|
| Text quick entry | `backend/bot/quick_entry/handlers.py` (`process_quick_entry_text`) | `text` |
| Voice quick entry | `backend/bot/quick_entry/handlers.py` (`handle_quick_entry_voice`) | `voice` |
| Receipt photo | `backend/bot/quick_entry/receipt_photo.py` (`handle_receipt_photo`) | `receipt` |

Each log line includes `family_budget_id`, Telegram user id, and the exception message.

**Deviation from phase prompt:** prompt said “4 sites in `handlers.py`”. Codebase has **3** true parser-except sites (2 in `handlers.py` + 1 in `receipt_photo.py`). All three instrumented. Other `MSG_MODEL_FAIL` branches (missing voice file path, provider not Google, `speech_status is None`, etc.) are not parser-except paths and were left as-is.

### Task 3 — catch-all handlers

- **Bot:** `register_global_error_handler(dp)` uses `@dp.errors()` / `ErrorEvent` (aiogram 3.29.1). Logs `telegram_user_id`, `update_id`, exception with full traceback via `logger.error(..., exc_info=event.exception)` (required because the exception is already bound on `ErrorEvent` — bare `logger.exception` would lose the traceback). Returns `True` so polling continues.
- **API:** `@app.exception_handler(Exception)` logs method/path + traceback (`exc_info=exc`), returns `JSONResponse` 500 `{"detail": "Internal Server Error"}`. Specific FastAPI handlers for `HTTPException` / validation errors remain more specific in the MRO lookup.

Orchestrator review note: worker initially used `logger.exception` in both catch-alls; bot path verified to print `NoneType: None` instead of a traceback when called outside an active `except`. Fixed to `exc_info=...` before this report.

---

## New / extended tests

- `tests/test_error_logging.py`
  - `test_setup_logging_writes_to_configured_file`
  - `TestParserFailureLogging.test_voice_parser_failure_logged_with_context`
  - `TestParserFailureLogging.test_receipt_parser_failure_logged_with_context`
- `tests/test_quick_entry_flow.py`
  - `TestModelFailure.test_parser_malformed_does_not_increment_unparsed` — extended with `caplog` checks for `entry_path=text` + ids + exception message

---

## Local log file evidence

Path: `/home/xon/Documents/finance-bot/backend/logs/app.log`  
(created during app/test runs; gitignored)

```
2026-08-05 14:17:05,596 ERROR phase16d.evidence phase16d durable logging evidence line
2026-08-05 14:20:17,300 ERROR phase16d.evidence phase16d durable logging evidence line entry_path=text family_budget_id=00000000-0000-0000-0000-000000000001 telegram_user_id=1: ParserMalformed('probe')
```

File is written by the running app/tests; size after full pytest ≈ 640KB+ (INFO traffic from the suite sharing the same handlers).

---

## Files touched

| Path | Change |
|------|--------|
| `backend/app/logging_setup.py` | **created** |
| `backend/tests/test_error_logging.py` | **created** |
| `backend/app/config.py` | `LOG_FILE_PATH` |
| `backend/app/main.py` | `setup_logging` + Exception handler |
| `backend/bot/main.py` | `setup_logging` + `@dp.errors()` handler |
| `backend/bot/quick_entry/handlers.py` | text/voice parser failure logs |
| `backend/bot/quick_entry/receipt_photo.py` | receipt parser failure log |
| `backend/tests/test_quick_entry_flow.py` | caplog on text malformed path |
| `.gitignore` | `logs/` |

No `docs/PRD.md` edits. No `docs/context/*` edits. No commit in this phase (not requested).
