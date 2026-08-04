# Phase 13 Task 2 Review — Google provider full-prompt path (no caching)

**Reviewer:** task-scoped gate  
**Base:** `373635d`  
**Head:** `f238c3b`  
**Scope:** `backend/app/parsing/http_adapter.py`, `backend/tests/test_phase13_prompt_caching.py`

---

## Verdict

| Gate | Result |
|------|--------|
| Spec compliance | ✅ |
| Code quality | **Approved** |

---

## 1. Spec compliance

### Required interfaces

| Requirement | Status | Evidence |
|-------------|--------|----------|
| `HttpParser` accepts `provider="google"` | ✅ | `parse` allows `("openai", "anthropic", "google")`. |
| POST to `…/v1beta/models/{model}:generateContent?key={api_key}` | ✅ | `_post` builds URL with `self._model`, passes `params={"key": self._api_key}`. Test asserts `generateContent`, model slug, and `key=test-key` in URL. |
| `systemInstruction` = `static_cache_text()` | ✅ | Request body uses `static_cache_text()` in `systemInstruction.parts[0].text`; test asserts equality. |
| User content = mutable payload | ✅ | Shared `user_content = build_mutable_parser_payload(request)` passed in `contents[0].parts[0].text`; test asserts parsed JSON `text` field. |
| Extract text from `candidates[0].content.parts[*].text` joined | ✅ | `_extract_text_from_provider_body` implements join loop per brief. |
| Model from constructor only — never hard-coded | ✅ | `model = self._model` in URL; no model string literals in diff. |
| Provider value exactly `"google"` | ✅ | Branch key and allow-list use lowercase `"google"`. |
| No `CachedContent` creation or reference | ✅ | No `cachedContent` in implementation; test asserts key absent from request body. |
| OpenAI path unchanged | ✅ | Still posts to OpenAI chat completions with `build_parser_messages(request)`. |
| Anthropic path unchanged | ✅ | Still posts with `IMMUTABLE_PARSER_INSTRUCTIONS` system + `user_content` message. |
| Consumes `static_cache_text`, `build_mutable_parser_payload`, shared retry/malformed logic | ✅ | Import added; `parse` loop and `_parse_operations_payload` untouched. |
| Backend only | ✅ | Two backend files changed. |
| Tests from task brief | ✅ | `test_google_full_prompt_parse_succeeds` and `test_google_unsupported_without_model` match brief. |

### Global constraints

| Constraint | Status |
|------------|--------|
| Provider value exactly `"google"` | ✅ |
| Model only from `PARSER_MODEL` / constructor | ✅ (`factory.py` already passes `PARSER_MODEL`; no factory change required for this task) |
| Static via `static_cache_text()` | ✅ |
| No CachedContent yet | ✅ |
| OpenAI / Anthropic unchanged | ✅ |
| Backend only | ✅ |

### Out of scope (correctly untouched)

- `google_cache.py` and cache-aware generate path — later tasks.
- `HttpParser` optional `prompt_cache` injection — later tasks.
- Factory / env wiring beyond existing `PARSER_PROVIDER` passthrough — not required here.

### Test / process claims (from implementer report)

Reported TDD order (1 fail / 1 pass → 7 pass in phase file, 8 pass quick-entry regression), commit `f238c3b`, and no stubs are consistent with diff scope. Review did not re-run the suite per gate instructions.

**Spec compliance: ✅**

---

## 2. Code quality

### Strengths

- **Minimal, focused diff** — google branch added without refactoring shared parse/retry/extraction plumbing.
- **Correct prompt split for Gemini** — static instructions in `systemInstruction`, mutable JSON in user `contents`; mirrors the phase-13 static/mutable contract from Task 1.
- **Defensive response parsing** — google extraction validates `candidates`, `content`, `parts`, and non-empty text list before join; consistent with openai/anthropic style.
- **Tests encode the transport contract** — URL shape, auth param, body fields, end-to-end parse, and empty-model guard.
- **Shared infrastructure reused** — `user_content`, retry on 429/5xx, `ParserMalformed` / `ParserUnavailable` semantics unchanged.

### Minor notes (non-blocking)

1. **`static_cache_text()` called on every google POST.** Acceptable for Task 2; same memoization note as Task 1 if this becomes hot-path in later tasks.
2. **`cachedContent` assertion is top-level only** (`"cachedContent" not in seen["body"]`). Matches the brief verbatim and is sufficient for this task; nested-key regression would need a deeper walk (not required now).
3. **No dedicated tests for malformed google response bodies** (empty `candidates`, missing `parts`). Consistent with existing openai/anthropic coverage in this file; shared `ParserMalformed` path is straightforward.
4. **Redundant `model = self._model` local** in google branch — mirrors brief snippet as documentation; harmless.

### Risks considered and dismissed

- **Google branch ordering** (openai → google → anthropic return) — mutually exclusive; equivalent to brief’s snippet.
- **API key in query param** — required by Gemini REST per task spec.
- **Empty-model test is provider-agnostic** — still valuable as brief-specified guard for google construction path.

No defects, security issues, or maintainability blockers found.

**Code quality: Approved**

---

## 3. Findings summary

### Critical / Important

None.

### Informational

- Consider memoizing `static_cache_text()` if later tasks call it on every parse.
- Malformed google response extraction could gain unit tests in a later task if coverage expansion is desired.

---

## 4. Disabled / stubbed / mocked

None reported; none observed in diff.
