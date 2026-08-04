# Phase 13 Task 1 Report — Prompt version + static/mutable assembly assertions

## Status

DONE

## Commit

- `373635d` — feat(parsing): add static cache text and prompt version id

## What was done

Added to `backend/app/parsing/prompt.py`:

- `STATIC_CACHE_BALLAST` — inert repeated `"ballast"` text (80 lines × 200 tokens joined by dots), prefixed with `# cache-ballast` header
- `static_cache_text()` — returns `IMMUTABLE_PARSER_INSTRUCTIONS + STATIC_CACHE_BALLAST`
- `prompt_version()` — first 16 hex chars of SHA-256 digest of `static_cache_text()`

Created `backend/tests/test_phase13_prompt_caching.py` with five assembly assertions from the task brief.

`IMMUTABLE_PARSER_INSTRUCTIONS` wording was not changed. `build_parser_messages()` still uses only `IMMUTABLE_PARSER_INSTRUCTIONS` in the system message (unchanged behaviour; verified by test).

## Test runs

### Before change (failing tests only, Step 2)

```
cd backend && ./venv/bin/pytest tests/test_phase13_prompt_caching.py -q
```

Result: **ERROR** — `ImportError: cannot import name 'prompt_version' from 'app.parsing.prompt'`

### After implementation (Task 1 file, Step 4)

```
cd backend && ./venv/bin/pytest tests/test_phase13_prompt_caching.py -q
```

Result: **5 passed** in 0.06s

### Regression (full backend suite excluding new file)

```
cd backend && ./venv/bin/pytest tests/ -q --ignore=tests/test_phase13_prompt_caching.py
```

Result: **382 passed**, 1 warning (pre-existing Starlette/httpx deprecation)

### Before commit (Task 1 file, final)

```
cd backend && ./venv/bin/pytest tests/test_phase13_prompt_caching.py -q
```

Result: **5 passed** in 0.06s

## Verification notes

- `len(static_cache_text())` = 128,866 chars → `// 4` = 32,216 (≥ 4096 required)
- `prompt_version()` matches `[0-9a-f]{16}`; changes when `STATIC_CACHE_BALLAST` is monkeypatched
- Static blob contains no family markers, no `wallet_names`, no `{text}` / `{wallet` substitution slots
- Mutable payload still holds request text and wallet names; those strings absent from static blob

## Self-review

| Check | Result |
|-------|--------|
| TDD order (fail → implement → pass) | Yes |
| `hashlib` import at top of file | Yes |
| Ballast separate from `IMMUTABLE_PARSER_INSTRUCTIONS` | Yes |
| No frontend / docs / AGENTS.md changes | Yes |
| `build_parser_messages` behaviour unchanged | Yes |
| Ballast contains no family-specific data | Yes |

No issues found in self-review.

## Disabled / stubbed / mocked / finish-later

None.
