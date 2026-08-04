# Phase 13 Task 2 Report — Google provider full-prompt path (no caching)

## Status

DONE

## Commit

- `f238c3b` — feat(parsing): add Google Gemini full-prompt provider branch

## What was done

Modified `backend/app/parsing/http_adapter.py`:

- `HttpParser.parse` accepts `provider="google"` alongside openai/anthropic
- `_post` posts to `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` with `key` query param; model from constructor only
- Request body: `systemInstruction` = `static_cache_text()`, `contents` = user role with mutable JSON payload
- `_extract_text_from_provider_body` joins `candidates[0].content.parts[*].text`
- OpenAI/Anthropic paths unchanged (`IMMUTABLE_PARSER_INSTRUCTIONS` / `build_parser_messages`)

Added to `backend/tests/test_phase13_prompt_caching.py`:

- `test_google_full_prompt_parse_succeeds` — mocks transport, asserts URL/body shape and parsed amount
- `test_google_unsupported_without_model` — empty model raises `ParserMalformed`

No CachedContent creation or reference.

## Test runs

### Before change (Task 1 tests only)

```
cd backend && ./venv/bin/pytest tests/test_phase13_prompt_caching.py -q
```

Result: **5 passed** in 0.07s

### After failing tests added, before implementation (Step 2)

```
cd backend && ./venv/bin/pytest tests/test_phase13_prompt_caching.py::test_google_full_prompt_parse_succeeds tests/test_phase13_prompt_caching.py::test_google_unsupported_without_model -q
```

Result: **1 failed, 1 passed** — `test_google_full_prompt_parse_succeeds` failed with `unsupported parser provider: 'google'`

### After implementation (Task 1+2 file)

```
cd backend && ./venv/bin/pytest tests/test_phase13_prompt_caching.py -q
```

Result: **7 passed** in 0.08s

### Regression (quick entry parser)

```
cd backend && ./venv/bin/pytest tests/test_quick_entry_parser.py -q
```

Result: **8 passed** in 0.08s

## Self-review

| Check | Result |
|-------|--------|
| TDD order (fail → implement → pass) | Yes |
| Model never hard-coded | Yes — `self._model` only |
| `static_cache_text()` as systemInstruction | Yes |
| No `cachedContent` in request | Yes — asserted in test |
| OpenAI/Anthropic unchanged | Yes — regression tests pass |
| Retry/malformed logic shared | Yes — same `parse` loop |

No issues found in self-review.

## Disabled / stubbed / mocked / finish-later

None.
