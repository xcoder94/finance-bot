# Phase 13 Task 5 Report — Measurement script + suite gate

## Status

DONE

## Commit

- `a3156b2` — chore(parsing): add live Gemini cache measurement script

## What was done

Created `backend/scripts/measure_prompt_cache.py`:

- Inserts `backend/` on `sys.path` for direct `python scripts/measure_prompt_cache.py` invocation (same pattern as other backend scripts)
- Reads `PARSER_PROVIDER`, `PARSER_API_KEY`, `PARSER_MODEL` from `app.config`
- Missing any of the three → prints `blocked: PARSER_* credentials not available`, exit 2
- Non-google provider with creds present → prints `unsupported provider: … (google only)`, exit 1
- Google path: `GooglePromptCache.ensure_cache()` → one `generateContent` with `cachedContent` → prints `promptTokenCount`, `cachedContentTokenCount`, `cached_ratio` (4 decimal places)
- Exit 0 if `cached_ratio >= 0.90`, else exit 1
- Never invents token counts or ratios

## Measurement script run

```bash
cd backend && ./venv/bin/python scripts/measure_prompt_cache.py
```

Stdout:

```
blocked: PARSER_* credentials not available
```

Exit code: **2**

## Test runs

### Backend (full suite)

```bash
cd backend && ./venv/bin/pytest -q
```

```
........................................................................ [ 18%]
........................................................................ [ 36%]
........................................................................ [ 54%]
........................................................................ [ 72%]
........................................................................ [ 90%]
....................................
=============================== warnings summary ===============================
venv/lib/python3.14/site-packages/fastapi/testclient.py:1
  /home/xon/Documents/finance-bot/backend/venv/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
396 passed, 1 warning in 20.84s
```

### Frontend (full suite)

```bash
cd frontend && npx vitest run --reporter=dot
```

```
 RUN  v4.1.10 /home/xon/Documents/finance-bot/frontend

·············································································································································································································

 Test Files  37 passed (37)
      Tests  205 passed (205)
   Start at  17:31:01
   Duration  1.87s (transform 1.32s, setup 0ms, import 3.20s, tests 618ms, environment 7ms)
```

## DEFERRED (live provider evidence)

Acceptance items requiring a live Gemini call and ≥90% `cached_ratio` are **blocked** in this environment — `PARSER_PROVIDER` / `PARSER_API_KEY` / `PARSER_MODEL` not set. No ratio invented. Customer can run `scripts/measure_prompt_cache.py` with credentials to obtain evidence.

Automated coverage that always runs without live provider: Task 1 assembly tests, Task 4 miss-fallback + stub transaction test (14 tests in `test_phase13_prompt_caching.py`).

## Self-review

| Check | Result |
|-------|--------|
| Missing creds → blocked message, exit 2 | Yes — verified |
| Google path: ensure_cache → cached generateContent | Yes — implemented |
| Ratio from API `usageMetadata` only | Yes — no invented numbers |
| Bootstrap imports from `app.*` | Yes |
| Backend ≥382 passed | Yes — 396 passed |
| Frontend 37 files / 205 tests | Yes |
| Frontend source untouched | Yes |
| Only measurement script committed | Yes |

No issues found in self-review.

## Disabled / stubbed / mocked / finish-later

None.
