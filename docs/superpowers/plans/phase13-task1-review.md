# Phase 13 Task 1 Review — Prompt version + static/mutable assembly

**Reviewer:** task-scoped gate  
**Base:** `85e6d050`  
**Head:** `373635d`  
**Scope:** `backend/app/parsing/prompt.py`, `backend/tests/test_phase13_prompt_caching.py`

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
| `STATIC_CACHE_BALLAST: str` — fixed inert text | ✅ | Constant matches task brief formula exactly (`# cache-ballast` header + 80 lines of 200×`ballast` joined by dots). |
| `len(static_cache_text()) // 4 >= 4096` | ✅ | Implementer reports 128,866 chars → 32,216 pseudo-tokens; formula yields ~128k chars, well above threshold. Test asserts `len(a) // 4 >= 4096`. |
| `static_cache_text()` = `IMMUTABLE_PARSER_INSTRUCTIONS + STATIC_CACHE_BALLAST` | ✅ | Direct concatenation in `static_cache_text()`. Test asserts `startswith(IMMUTABLE_PARSER_INSTRUCTIONS)` and stability. |
| `prompt_version()` = first 16 hex chars of SHA-256 of static text | ✅ | `hashlib.sha256(static_cache_text().encode("utf-8")).hexdigest()[:16]`. Test asserts `[0-9a-f]{16}` and change on ballast mutation. |
| Ballast appended separately; `IMMUTABLE_PARSER_INSTRUCTIONS` wording unchanged | ✅ | Diff shows instructions block byte-identical to base commit; ballast is a separate constant. |
| `build_parser_messages()` unchanged (system = bare instructions) | ✅ | `build_parser_messages` not modified; dedicated test + existing `test_quick_entry_parser.py` coverage. |
| Backend only; no frontend/docs/AGENTS.md | ✅ | Two backend files only. |
| Tests from task brief | ✅ | All five tests present and match brief verbatim. |
| `hashlib` import at top of file | ✅ | First import in `prompt.py`. |

### Global constraints

| Constraint | Status |
|------------|--------|
| Static body = instructions + inert ballast; no family data in static | ✅ Tests assert sample wallet names, message text, category-like markers, `wallet_names`, and `{text}` / `{wallet` slots are absent from static blob. Ballast is ASCII `"ballast"` repetitions only. |
| Do not change `IMMUTABLE_PARSER_INSTRUCTIONS` wording | ✅ Confirmed against base commit `85e6d050`. |

### Out of scope (correctly untouched)

- `build_parser_messages` still sends `IMMUTABLE_PARSER_INSTRUCTIONS` (not `static_cache_text()`) in the system message — correct for Task 1; Google cache wiring is later tasks.
- No wiring of `prompt_version()` or `static_cache_text()` into parser factory yet — not required here.

### Test / process claims (from implementer report)

Reported TDD order (fail on import → implement → 5 pass), regression 382 pass, and commit `373635d` are consistent with diff scope. Review did not re-run the suite per gate instructions.

**Spec compliance: ✅**

---

## 2. Code quality

### Strengths

- **Minimal, focused diff** — only the three new symbols plus `hashlib` import; no drive-by refactors.
- **Tests encode the phase contract** — stability, size floor, separation of static vs mutable, version derivation, and backward-compatible message assembly are all covered.
- **Ballast design is appropriate** — deterministic, ASCII-only, no PII/family-specific strings; comment documents Gemini cache minimum rationale.
- **Follows existing module style** — same string-constant pattern as `IMMUTABLE_PARSER_INSTRUCTIONS`, typed return annotations, no new dependencies.

### Minor notes (non-blocking)

1. **`static_cache_text()` recomputes concatenation on each call.** For Task 1 this is fine; if hot-path callers appear in later tasks, a module-level `_STATIC_CACHE_TEXT` cache would avoid repeated ~129 KB concatenation. Not required now.
2. **Overlap with `test_quick_entry_parser.py::test_prompt_immutable_then_mutable_order`.** The new test duplicates message-order coverage. Acceptable for phase-scoped regression; could be deduplicated later if desired.
3. **Implementer report wording** — describes ballast as "200 tokens" per line; code uses 200 repetitions of the word `"ballast"`. Report imprecision only; implementation matches brief.

### Risks considered and dismissed

- **Large module constant (~129 KB)** — intentional for explicit-cache token minimum; loaded once at import.
- **`FAMILY_MARKERS` includes strings not in `_sample_request()`** (`Алишер`, `2026-08-04`) — defensive negative assertions; harmless.
- **Word "family" in `IMMUTABLE_PARSER_INSTRUCTIONS`** — generic instruction text, not per-family data; consistent with global constraint intent.

No defects, security issues, or maintainability blockers found.

**Code quality: Approved**

---

## 3. Findings summary

### Critical / Important

None.

### Informational

- Consider memoizing `static_cache_text()` result if later tasks call it on every parse (optional optimization).
- Phase test partially duplicates existing parser message-order test.

---

## 4. Disabled / stubbed / mocked

None reported; none observed in diff.
