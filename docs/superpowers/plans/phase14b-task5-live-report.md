# Phase 14b Task 5 — Live verification + suite gate report

Date: 2026-08-04  
Agent environment: Cursor sandbox

## Environment blockers

1. **`.env` unreadable** — blocked by `.cursorignore`; agent sees empty Permission denied file. `PARSER_PROVIDER`, `PARSER_API_KEY`, `PARSER_MODEL` not loaded. `/tmp/finance-bot-test-env.sh` sets test DB/BOT vars only, not `PARSER_*`.
2. **PostgreSQL unavailable** — nothing listening on `localhost:5432` (`ConnectionRefusedError`). Docker socket unavailable. DB-dependent pytest cases fail/skip.

## Step 1: `measure_prompt_cache.py`

Command:

```bash
cd backend && source /tmp/finance-bot-test-env.sh && ./venv/bin/python scripts/measure_prompt_cache.py
```

Verbatim output:

```
blocked: PARSER_* credentials not available
```

Exit code: **2**  
HTTP: **N/A** (credentials missing before any request)

## Step 2–3: Audio smoke (`smoke_voice_audio.py`)

Script: `backend/scripts/smoke_voice_audio.py` — loads `PARSER_*`, reads `.ogg` path, builds `ParseRequest` with `audio_base64` + `audio/ogg`, calls `HttpParser.parse`, prints `ParseResponse` JSON and summary fields.

### Sample provenance

| File | How produced |
|------|----------------|
| `/tmp/noise-tone.ogg` | `ffmpeg -y -f lavfi -i "sine=f=440:d=2" -c:a libopus /tmp/noise-tone.ogg` (440 Hz tone, 2 s — not speech) |
| `/tmp/silence.ogg` | `ffmpeg -y -f lavfi -i anullsrc=r=16000:cl=mono -t 2 -c:a libopus /tmp/silence.ogg` (silence, 2 s) |

`espeak` not installed; no Russian speech sample.

### Noise sample

```bash
./venv/bin/python scripts/smoke_voice_audio.py /tmp/noise-tone.ogg
```

Verbatim output:

```
blocked: PARSER_* credentials not available
```

Exit code: **2**

### Silence sample

```bash
./venv/bin/python scripts/smoke_voice_audio.py /tmp/silence.ogg
```

Verbatim output:

```
blocked: PARSER_* credentials not available
```

Exit code: **2**

Live `speech_status=not_recognized` check: **not run** (blocked by missing `PARSER_*`).

## Step 4: Test suites

### Backend

```bash
cd backend && source /tmp/finance-bot-test-env.sh && ./venv/bin/pytest -q
```

Summary line:

```
14 failed, 123 passed, 278 skipped, 1 warning, 2 errors in 10.82s
```

Exit code: **1**

Failures/errors: all traced to `ConnectionRefusedError: Connect call failed ('127.0.0.1', 5432)` on DB acceptance tests (`test_phase3_budget_name`, `test_phase9_members`, `test_quick_entry_schema`, `test_telegram_auth`).

Phase 14b unit tests (mocked parser, no DB): pass within skipped bulk.

### Frontend

```bash
cd frontend && npx vitest run --reporter=dot
```

Summary:

```
 Test Files  37 passed (37)
      Tests  205 passed (205)
   Start at  21:25:24
   Duration  2.41s (transform 1.66s, setup 0ms, import 4.21s, tests 780ms, environment 8ms)
```

Exit code: **0** — matches expected **205/37**.

Note: vitest emitted `kill EACCES` / worker-termination warnings in sandbox; all tests passed.

## Disabled / stubbed / mocked

None introduced in this task.

## Conclusion

| Check | Result |
|-------|--------|
| Prompt cache live (≥90% cached ratio) | **Blocked** — no `PARSER_*` |
| Voice parse live | **Blocked** — no `PARSER_*` |
| `speech_status` on silence/noise | **Blocked** — no `PARSER_*` |
| Backend pytest gate | **14F / 2E / 278S** — DB down |
| Frontend vitest gate | **205/37 pass** |

Live Gemini verification requires operator-run with real `.env` on a host with network + `PARSER_*` set.
