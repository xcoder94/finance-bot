# Phase 13 Task 4 Review — Wire Gemini cache into HttpParser

**Reviewer:** task-scoped gate  
**Base:** `367f102`  
**Head:** `5828c43`  
**Scope:** `backend/app/parsing/http_adapter.py`, `backend/tests/test_phase13_prompt_caching.py`

---

## Verdict

| Gate | Result |
|------|--------|
| Spec compliance | ✅ |
| Code quality | **Approved** |

---

## 1. Spec compliance

### Required interfaces (`HttpParser` wiring)

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Cached path: `cachedContent` set, no `systemInstruction` | ✅ | `_post_google` branches on `cache_name`; `test_cached_parse_references_cache_not_static` asserts both. |
| 404 / cache-missing 400 → `clear_local`, fall through to full-prompt once | ✅ | `_is_cache_missing_response` + `_post_google_flow` clears local and retries with `cache_name=None`. |
| Full-prompt path: `systemInstruction=static_cache_text()` | ✅ | `_post_google` else branch; asserted in miss test. |
| After successful full-prompt (no cache used): fire-and-forget `_rebuild_cache()` → `ensure_cache()` | ✅ | `google_cache_used=False` branch schedules `_rebuild_cache`; miss test asserts background POST `/cachedContents`. |
| After successful cached response: fire-and-forget `extend_ttl(name)` | ✅ | `google_cache_used=True` branch schedules `_extend_cache_ttl`; errors logged, not raised. |
| Optional `prompt_cache` injection; auto-construct for `provider=="google"` | ✅ | `__init__` uses `prompt_cache or GooglePromptCache(...)`. |
| Optional `on_rebuild` hook for tests | ✅ | Called at start of `_rebuild_cache`. |
| Background tasks retained via `_bg_tasks` + `done_callback` | ✅ | `_schedule_background` matches brief pattern. |
| `_post_google(client, request, *, cache_name=...)` split | ✅ | Extracted; `_post` delegates google path to it. |

### Global constraints

| Constraint | Status |
|------------|--------|
| Missing/expired cache must never fail user parse | ✅ Empty-list miss test parses 25000 and schedules rebuild; 404 fallback implemented inline. |
| Cached path must not resend static `systemInstruction` | ✅ Tested. |
| `clear_local` on cache miss | ✅ On 404/cache 400 in `_post_google_flow`. |
| Exactly one installation cache (manager already exists) | ✅ Rebuild delegates to `GooglePromptCache.ensure_cache()` reconcile logic from Task 3. |
| Stub parser path still creates transaction (skip if no Postgres) | ✅ `test_stub_parser_path_still_creates_transaction` with `@pytest.mark.skipif`. |
| No hard-coded model | ✅ URL uses `self._model` only; tests use `test-model-from-env`. |
| No fake ≥90% numbers in tests | ✅ None added. |
| Backend only | ✅ Two backend files changed. |

### Tests from task brief

| Test | Status |
|------|--------|
| `test_missing_cache_still_parses_and_schedules_rebuild` | ✅ Matches brief (empty list → full-prompt → background create). |
| `test_cached_parse_references_cache_not_static` | ✅ Matches brief. |
| `test_stub_parser_path_still_creates_transaction` | ✅ StubParser → `create_quick_entry_expense` → `txn.amount == 25000`. |

### Test / process claims (from implementer report)

| Claim | Status |
|-------|--------|
| Before: 11 passed; after: 14 passed | ✅ Re-run: **14 passed** in 3.02s (`tests/test_phase13_prompt_caching.py`). |
| Regression quick-entry + caching: 22 passed | ✅ Re-run: **22 passed** in 3.02s. |
| Commit `5828c43` | ✅ Verified. |
| No stubs / mocks beyond MockTransport + StubParser | ✅ |
| TDD order | ✅ Consistent with brief and diff. |

**Spec compliance: ✅**

---

## 2. Code quality

### Strengths

- **Clean flow separation** — `_post_google_flow` owns hit/miss orchestration; `_post_google` owns request shape; background work isolated in `_schedule_background` / `_rebuild_cache` / `_extend_cache_ttl`.
- **Correct user-path semantics** — cache miss fallback is synchronous within the request; rebuild and TTL extend never block or fail the parse response.
- **Retry loop preserved** — cached 404 fallback returns the full-prompt response into the existing attempt/retry loop; subsequent retries see cleared local state.
- **Tests encode the contract** — request body shape, rebuild side-effect, and DB transaction path without cache dependency.
- **Minimal scope** — only `http_adapter.py` and test file; factory unchanged (auto-constructed cache on google provider is sufficient).

### Minor notes (non-blocking)

1. **404 cached-path fallback not explicitly tested.** `test_missing_cache_still_parses_and_schedules_rebuild` covers empty local registry (no `cachedContent` attempt). Implementation handles 404/cache-400 on a cached `generateContent` call, but no test drives that branch. Low risk given mirror logic and Task 3 local registry.
2. **`extend_ttl` PATCH not asserted.** `test_cached_parse_references_cache_not_static` registers a PATCH handler but does not record calls (unlike rebuild test's `rebuild_calls`). Background TTL extend is fire-and-forget per spec; optional assertion would tighten coverage.
3. **`on_rebuild` hook untested.** Present for testability; brief marks it optional.
4. **Rebuild on every full-prompt success.** By design per brief step 4; concurrent parses may spawn redundant `ensure_cache` tasks. `ensure_cache` reconcile is idempotent — acceptable for MVP.
5. **Separate httpx clients when no client injected at init.** `HttpParser.parse()` and `GooglePromptCache.ensure_cache()` each may create their own client. Pre-existing Task 3 pattern; not introduced by this diff.

### Risks considered and dismissed

- **Broad 400 detection (`"cache"` in body)** — only evaluated on cached-path responses; matches brief "cache-missing style error".
- **Background rebuild failure** — `ensure_cache` soft-fails; user already has parse result.
- **extend_ttl failure** — caught and logged; does not affect response.

No defects, security issues, or maintainability blockers found.

**Code quality: Approved**

---

## 3. Findings summary

### Critical / Important

None.

### Informational

- Add an integration-style test for stale local name → cached `generateContent` 404 → `clear_local` → full-prompt success if coverage of the inline fallback is desired.
- Optionally assert PATCH in cached-hit test or use `on_rebuild` in miss test for deterministic scheduling without `asyncio.sleep(0.05)`.

---

## 4. Disabled / stubbed / mocked

None reported; none observed in diff.
