# Phase 13 Task 3 Review — Gemini explicit cache manager

**Reviewer:** task-scoped gate  
**Base:** `f238c3b`  
**Head:** `367f102`  
**Scope:** `backend/app/parsing/google_cache.py`, `backend/tests/test_phase13_prompt_caching.py`

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
| `CACHE_DISPLAY_PREFIX = "chontak-parser-"` | ✅ | Module constant. |
| `cache_display_name(version) -> str` → `chontak-parser-{version}` | ✅ | `f"{CACHE_DISPLAY_PREFIX}{version}"`. |
| `DEFAULT_CACHE_TTL_SECONDS = 604800` | ✅ | Module constant; used in create and `extend_ttl` default. |
| `GooglePromptCache.__init__(api_key, model, client=None)` | ✅ | Stores key/model/client; process-local `_local_name` / `_local_version`. |
| `ensure_cache() -> str \| None` — reconcile, create/reuse, soft-fail | ✅ | Lists caches; deletes prefix entries whose `displayName` ≠ current; reuses match or POSTs; wrapped in try/except returning `None`. |
| `delete_installation_caches()` — list + delete all prefix caches | ✅ | Iterates list, deletes every `displayName` starting with prefix; calls `clear_local()`. |
| `create_cache() -> str` — hard create, raise on failure | ✅ | Calls `_create`; `raise_for_status` / `RuntimeError` on bad response; not soft-wrapped. |
| `extend_ttl(name, ttl_seconds=604800)` | ✅ | PATCH to `{_BASE}/{name}` with `{"ttl": f"{ttl_seconds}s"}`; logs warning on ≥400. |
| `get_cached_name()` / `clear_local()` — process-local registry | ✅ | `get_cached_name` returns `None` when `_local_version != prompt_version()`. |
| Consumes `prompt_version`, `static_cache_text`, httpx | ✅ | Imports and uses all three. |
| Create body: `systemInstruction` = `static_cache_text()` only | ✅ | `_create` payload; test asserts text equality and absence of `FAMILY_MARKERS`. |
| Create body: `model` = `models/{self._model}` | ✅ | No hard-coded model; test asserts `models/test-model-from-env`. |
| Create body: `displayName` = `cache_display_name(prompt_version())` | ✅ | Asserted in create test. |
| Exactly one installation cache per version | ✅ | Stale prefix entries deleted before reuse/create; reuse test proves no duplicate POST. |
| `ensure_cache` never raises to caller | ✅ | Top-level try/except; `test_ensure_cache_returns_none_on_failure`. |
| HttpParser not wired | ✅ | No changes to `http_adapter.py` or factory; `GooglePromptCache` only referenced in tests. |
| Module-level shared-instance helpers | — | Optional per brief (“keep it simple”); correctly omitted. |

### Global constraints

| Constraint | Status |
|------------|--------|
| Exactly one installation-wide cache | ✅ |
| `displayName` = `chontak-parser-{version}` | ✅ |
| Delete old caches on version change | ✅ |
| `static_cache_text()` only — no family data | ✅ |
| Model from constructor — never hard-coded | ✅ |
| Soft `ensure_cache` returns `None` on failure | ✅ |
| No HttpParser wiring yet | ✅ |

### Tests from task brief

| Test | Status |
|------|--------|
| `test_ensure_cache_creates_with_static_only` | ✅ Matches brief (empty list → POST with static-only body). |
| `test_prompt_version_change_deletes_old_cache` | ✅ Refined per brief: stale prefix deleted, exactly one POST for new cache. |
| Reuse when list already has current `displayName` | ✅ `test_ensure_cache_reuses_matching_display_name` (brief refinement). |
| Soft-fail on list error | ✅ `test_ensure_cache_returns_none_on_failure` (implementation addition). |

### Test / process claims (from implementer report)

| Claim | Status |
|-------|--------|
| TDD order (module missing → implement → pass) | ✅ Consistent with diff and brief steps. |
| Before: 7 passed; after: 11 passed | ✅ Re-run: **11 passed** in 0.10s (`tests/test_phase13_prompt_caching.py`). |
| Quick-entry regression 8 passed | Not re-run this gate; scope is isolated new module + tests. |
| Commit `367f102` | ✅ Verified. |
| No stubs / mocks beyond MockTransport | ✅ |

**Spec compliance: ✅**

---

## 2. Code quality

### Strengths

- **Faithful to approved sketch** — implementation matches the task brief’s reference module with no scope creep.
- **Correct reconcile semantics** — list → delete stale prefix → reuse or create; local short-circuit when version matches.
- **Appropriate failure layering** — soft `ensure_cache`, hard `create_cache`, warn-only delete/TTL extend (404-tolerant delete).
- **Client ownership handled cleanly** — `owns` flag creates ephemeral client only when none injected; always closed in `finally`.
- **Tests encode the REST contract** — create payload shape, model slug, family-data exclusion, stale deletion, reuse without POST, soft failure.
- **No new dependencies** — httpx only, as required.

### Minor notes (non-blocking)

1. **`delete_installation_caches`, `create_cache`, `extend_ttl` untested directly.** Acceptable for Task 3; `ensure_cache` path exercises list/create/delete. Dedicated unit tests can land in Task 4 if wiring needs them.
2. **Local short-circuit not tested** — second `ensure_cache()` with same version should skip HTTP when local is warm. Low risk; logic is one guard at top of `_ensure_cache`.
3. **`ensure_cache` failure does not call `clear_local()`.** On a fresh instance (tested) both return `None`. If a prior success populated local and a later reconcile fails, `get_cached_name()` could still return the stale name while `ensure_cache()` returns `None`. Worth watching when Task 4 wires the cache into parse; not a Task 3 blocker.
4. **List API pagination not handled.** Gemini may paginate `cachedContents`; brief sketch omits it. Acceptable for MVP; note if production cache counts grow.
5. **Duplicate `displayName` entries** — loop keeps last matching name but does not delete other prefix entries with the same `displayName`. Unlikely in normal operation after reconcile.

### Risks considered and dismissed

- **Partial delete then create failure** — installation may be left without cache but caller gets `None`; matches soft-ensure contract.
- **`delete_installation_caches` propagates list errors** — spec does not require soft-fail; callers are internal/administrative.
- **Report wording “local cleared” on failure** — test only covers fresh instance; behavior is “unset stays unset,” not explicit `clear_local()`. Harmless.

No defects, security issues, or maintainability blockers found.

**Code quality: Approved**

---

## 3. Findings summary

### Critical / Important

None.

### Informational

- Consider invalidating local registry inside `ensure_cache` except block if Task 4 needs strict `ensure_cache` / `get_cached_name` agreement after transient failures.
- Pagination and duplicate-displayName edge cases may deserve follow-up if cache management becomes operational concern.
- Direct tests for `extend_ttl` and `delete_installation_caches` optional in Task 4.

---

## 4. Disabled / stubbed / mocked

None reported; none observed in diff.
