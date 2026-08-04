# Phase 13 Task 4 Report — Wire cache into Google parse

## Status

DONE

## Commit

- `5828c43` — feat(parsing): use Gemini cache with full-prompt fallback

## What was done

Modified `backend/app/parsing/http_adapter.py`:

- Optional `prompt_cache` and `on_rebuild` on `HttpParser.__init__`; auto-constructs `GooglePromptCache` when `provider=="google"`
- `_post_google(client, request, cache_name=...)` — cached path sends `cachedContent` only; full-prompt sends `systemInstruction=static_cache_text()`
- `_post_google_flow` — tries local cache name; on 404 / cache-related 400 clears local and falls through to full-prompt once
- After successful full-prompt (no cache used): fire-and-forget `_rebuild_cache()` → `ensure_cache()`
- After successful cached response: fire-and-forget `_extend_cache_ttl()` with exception logging
- `_bg_tasks` set retains background tasks until completion

Added to `backend/tests/test_phase13_prompt_caching.py`:

- `test_missing_cache_still_parses_and_schedules_rebuild` — empty list → full-prompt parse; background `ensure_cache` creates cache
- `test_cached_parse_references_cache_not_static` — local name set → `cachedContent` without `systemInstruction`
- `test_stub_parser_path_still_creates_transaction` — `StubParser` → `create_quick_entry_expense`; skips if Postgres down

## Test runs

### Before change (Tasks 1–3)

```
cd backend && ./venv/bin/pytest tests/test_phase13_prompt_caching.py -q
```

Result: **11 passed** in 0.08s

### After implementation

```
cd backend && ./venv/bin/pytest tests/test_phase13_prompt_caching.py -q
```

Result: **14 passed** in 3.02s

### Regression (quick entry parser)

```
cd backend && ./venv/bin/pytest tests/test_quick_entry_parser.py tests/test_phase13_prompt_caching.py -q
```

Result: **22 passed** in 3.04s

## Self-review

| Check | Result |
|-------|--------|
| TDD order (tests → implement → pass) | Yes |
| Cache hit: `cachedContent`, no `systemInstruction` | Yes — tested |
| Cache miss: `clear_local`, full-prompt fallback | Yes — 404/400 cache detection |
| Background rebuild after full-prompt | Yes — not awaited in request path |
| Background `extend_ttl` after cache hit | Yes — errors logged, not raised |
| No hard-coded model names | Yes — `self._model` only |
| No invented ≥90% token ratios | Yes |
| Stub path proves cache not required for txn create | Yes — DB test with skipif |
| Frontend / forbidden docs untouched | Yes |

No issues found in self-review.

## Disabled / stubbed / mocked / finish-later

None.
