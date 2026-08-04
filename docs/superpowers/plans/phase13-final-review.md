# Phase 13 Final Review — Prompt caching (Google Gemini explicit cache)

**Reviewer:** whole-branch gate  
**Base:** `bd67301` (merge-base with main)  
**Head:** `a3156b2`  
**Branch scope:** `backend/app/parsing/{prompt,google_cache,http_adapter}.py`, `backend/tests/test_phase13_prompt_caching.py`, `backend/scripts/measure_prompt_cache.py`, plan doc

---

## Verdict

| Assessment | Result |
|------------|--------|
| Code-level acceptance intent | **Ready** |
| Task 5 gate | Spec ✅ · Quality **Approved** |

---

## Acceptance intent (code-level)

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Provider `"google"` | ✅ | `HttpParser` allows `google`; factory passes `PARSER_PROVIDER`; google REST + extraction in `http_adapter.py`. |
| Model from `PARSER_MODEL` only | ✅ | All URLs/bodies use `self._model` / env; tests assert `test-model-from-env`; no hard-coded model strings. |
| Static = `IMMUTABLE` + ballast; no family data | ✅ | `static_cache_text()`; openai/anthropic still use bare `IMMUTABLE_PARSER_INSTRUCTIONS`; 5 assembly tests + create-body assertions. |
| One installation cache; delete on version change | ✅ | `GooglePromptCache.ensure_cache()` lists by `chontak-parser-` prefix, deletes stale displayNames, reuses or creates one; version from `prompt_version()` hash. |
| Miss → full-prompt + background rebuild | ✅ | `_post_google_flow` full-prompt when no local name; schedules `_rebuild_cache` → `ensure_cache`; miss integration test. |
| No user-facing changes | ✅ | Backend parsing only; no `frontend/src` changes; no bot copy changes in diff. |
| Measure script blocked without inventing ratio | ✅ | Exit 2 + exact blocked message when creds absent; ratio only from live `usageMetadata`. |

---

## Test / suite gate

| Check | Status |
|-------|--------|
| Phase 13 test file | 14 tests — assembly, google transport, cache CRUD, miss/hit paths, stub transaction |
| Backend regression | Report: **396 passed** (baseline 382 + 14; no deletions) |
| Frontend unchanged | Report: **37 files, 205 tests** |
| Stubs / mocks | MockTransport + StubParser + optional Postgres skip only |

---

## Deferred (expected, not a code defect)

| Item | Status |
|------|--------|
| Live ≥90% `cached_ratio` on real Gemini | **Blocked** — no `PARSER_*` in environment; `measure_prompt_cache.py` exit 2 documented. Customer runs script with credentials before manual acceptance step 1. |

---

## Findings

### Critical

None.

### Important

1. **Live cache-efficiency evidence still outstanding** — automated path is correct and blocked honestly; hand acceptance step 1 requires one successful `measure_prompt_cache.py` run (exit 0) with customer credentials.
2. **Cold-start parse uses full prompt until background rebuild completes** — first google parse after deploy/restart does not wait for cache; subsequent parses use cache. Matches spec §5; worth knowing for manual step 2 timing.

### Informational (non-blocking)

- Cached-path 404 → full-prompt fallback implemented but not covered by a dedicated test (carried from Task 4 review).
- `extend_ttl` PATCH not asserted in cached-hit test (fire-and-forget per spec).

---

## Disabled / stubbed / mocked / finish-later

None in implementation. Live ≥90% measurement listed under **Deferred** above.

---

## Commits reviewed

1. `373635d` — static cache text + prompt version  
2. `f238c3b` — Google full-prompt provider branch  
3. `367f102` — Gemini explicit cache manager  
4. `5828c43` — cache wiring + fallback  
5. `a3156b2` — measurement script  
6. `85e6d05` — plan doc (docs only)
