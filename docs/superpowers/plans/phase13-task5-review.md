# Phase 13 Task 5 Review — Measurement script + suite gate

**Reviewer:** task-scoped gate  
**Base:** `5828c43`  
**Head:** `a3156b2`  
**Scope:** `backend/scripts/measure_prompt_cache.py`

---

## Verdict

| Gate | Result |
|------|--------|
| Spec compliance | ✅ |
| Code quality | **Approved** |

---

## 1. Spec compliance

### Required behaviour

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Create `backend/scripts/measure_prompt_cache.py` | ✅ | Sole file in diff; commit `a3156b2`. |
| Bootstrap: backend on `sys.path` (script-style) | ✅ | `Path(__file__).resolve().parents[1]` + `sys.path.insert`; matches brief note and repo script pattern. |
| Read `PARSER_PROVIDER`, `PARSER_API_KEY`, `PARSER_MODEL` from config | ✅ | Imports from `app.config`. |
| Missing any → `blocked: PARSER_* credentials not available`, exit 2 | ✅ | `_BLOCKED_MSG` exact; `main()` raises `SystemExit(2)`. |
| Google path: `ensure_cache()` → `generateContent` with `cachedContent` | ✅ | `_measure()`; no `systemInstruction` in body. |
| Model from `PARSER_MODEL` only | ✅ | URL uses `PARSER_MODEL`; cache ctor uses same. |
| Print `promptTokenCount`, `cachedContentTokenCount`, `cached_ratio` (4 dp) | ✅ | Lines 81–83. |
| Exit 0 if `cached_ratio >= 0.90`, else exit 1 | ✅ | Line 85. |
| Never invent token counts or ratio | ✅ | Ratio only when both fields are ints from `usageMetadata`; invalid/missing → stderr + exit 1. |
| No live call required in CI | ✅ | Script is opt-in; blocked path needs no network. |
| Run once in environment; record blocked exit 2 | ✅ | Report documents stdout + exit 2. |
| Backend suite ≥382; frontend 37 files / 205 tests | ✅ | Report: 396 passed; 37 / 205 — counts meet gate. |
| Only measurement script in commit | ✅ | Diff is 1 file. |

### Extra behaviour (non-spec, acceptable)

| Behaviour | Notes |
|-----------|-------|
| Non-`google` provider with creds present → exit 1 + message | Reasonable guard; does not weaken blocked path. |
| `ensure_cache` failure → exit 1 stderr | Correct failure mode; no fabricated ratio. |

**Spec compliance: ✅**

---

## 2. Code quality

### Strengths

- **Correct measurement contract** — mirrors production cached request shape (mutable user payload + `cachedContent` only).
- **Strict metadata handling** — refuses to compute ratio without valid API fields.
- **Clear exit semantics** — 2 blocked, 1 failure/low ratio, 0 pass.
- **Minimal scope** — 101-line standalone script; no production wiring changes.

### Minor notes (non-blocking)

1. **Separate httpx clients** — `GooglePromptCache` and `generateContent` each open a client; fine for a one-off measurement script.
2. **`cached_count == 0` allowed** — yields ratio 0 and exit 1; honest, not invented.
3. **No unit test for the script** — brief explicitly excludes live CI call; acceptable.

No defects or maintainability blockers.

**Code quality: Approved**

---

## 3. Findings summary

### Critical / Important

None.

### Informational

- Customer must run the script with live `PARSER_*` credentials to satisfy phase acceptance step 1 (≥90%); blocked here by design.

---

## 4. Disabled / stubbed / mocked

None reported; none observed in diff.
