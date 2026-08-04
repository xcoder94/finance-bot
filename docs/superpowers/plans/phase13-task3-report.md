# Phase 13 Task 3 Report — Gemini explicit cache manager

## Status

DONE

## Commit

- `367f102` — feat(parsing): add Gemini explicit prompt-cache manager

## What was done

Created `backend/app/parsing/google_cache.py`:

- `CACHE_DISPLAY_PREFIX`, `DEFAULT_CACHE_TTL_SECONDS`, `cache_display_name(version)`
- `GooglePromptCache` with `ensure_cache`, `delete_installation_caches`, `create_cache`, `extend_ttl`, `get_cached_name`, `clear_local`
- `ensure_cache` lists installation caches, deletes any with prefix whose `displayName` ≠ current version, reuses matching entry or creates one; soft-fails (`None`) on exception
- Create payload: `systemInstruction` = `static_cache_text()`, `model` = `models/{self._model}`, TTL 604800s
- Process-local registry keyed to `prompt_version()`

Added to `backend/tests/test_phase13_prompt_caching.py`:

- `test_ensure_cache_creates_with_static_only` — empty list → POST with static-only body, no family markers
- `test_prompt_version_change_deletes_old_cache` — stale prefix cache deleted, new one created
- `test_ensure_cache_reuses_matching_display_name` — existing matching displayName reused, no POST
- `test_ensure_cache_returns_none_on_failure` — list 500 → `None`, local cleared

HttpParser not wired (Task 4).

## Test runs

### Before change (Tasks 1–2 only)

```
cd backend && ./venv/bin/pytest tests/test_phase13_prompt_caching.py -q
```

Result: **7 passed** in 0.08s

### After failing tests added, before implementation (Step 2)

```
cd backend && ./venv/bin/pytest tests/test_phase13_prompt_caching.py -q
```

Result: **ERROR** — `ModuleNotFoundError: No module named 'app.parsing.google_cache'`

### After implementation

```
cd backend && ./venv/bin/pytest tests/test_phase13_prompt_caching.py -q
```

Result: **11 passed** in 0.10s

### Regression (quick entry parser)

```
cd backend && ./venv/bin/pytest tests/test_quick_entry_parser.py -q
```

Result: **8 passed** in 0.07s

## Self-review

| Check | Result |
|-------|--------|
| TDD order (fail → implement → pass) | Yes |
| Model never hard-coded | Yes — `self._model` only |
| `static_cache_text()` in cache create | Yes |
| No family data in cache body | Yes — asserted in test |
| Exactly one installation cache per version | Yes — delete stale prefix, reuse or create |
| `ensure_cache` never raises to caller | Yes — try/except returns `None` |
| HttpParser not wired | Yes |
| No new packages | Yes |

No issues found in self-review.

## Disabled / stubbed / mocked / finish-later

None.
