# Report — fix/income-type-and-demo-data-removal

Branch: `fix/income-type-and-demo-data-removal`  
Date: 2026-08-06  
Orchestrator: Cursor Grok 4.5  
Workers: composer-2.5 (all three tasks)

---

## RAW GIT LOG

```
b5da2f7 Remove demo transaction seeding and clear-demo feature.
54867b5 Add one-off script to clear seeded demo transactions across budgets.
87aca28 fix(parser): classify bare kirim/chiqim messages by direction word
```

Fuller:

```
commit b5da2f7080009d2992271e2683f89f88ea43facb
Author:     xcoder94 <o7451155@yandex.com>
AuthorDate: Thu Aug 6 10:27:33 2026 +0500

    Remove demo transaction seeding and clear-demo feature.

    New budgets no longer get fake transactions; demo API, service, Settings
    control, and seed helpers are deleted. Cleanup script uses soft_delete directly.

commit 54867b5a2e62a378c9e33a83e48b5d033c0f81d9
Author:     xcoder94 <o7451155@yandex.com>
AuthorDate: Thu Aug 6 10:22:28 2026 +0500

    Add one-off script to clear seeded demo transactions across budgets.

    Soft-deletes is_demo transactions for every family budget that still has them, with a localhost safety gate before any writes.

commit 87aca28109036b4438eb5441ecce2e9351ca146b
Author:     xcoder94 <o7451155@yandex.com>
AuthorDate: Thu Aug 6 10:19:39 2026 +0500

    fix(parser): classify bare kirim/chiqim messages by direction word

    Gemini defaulted bare income messages to expense because the system prompt
    had no rule for unambiguous direction words without a category match.
```

Base (main): `9eb378b`

Diffstat `main...HEAD`:

```
 backend/app/api/v1/demo_data.py                   |  38 ---
 backend/app/main.py                               |   2 -
 backend/app/parsing/prompt.py                     |   4 +
 backend/app/parsing/stub.py                       |  36 +++
 backend/app/services/budget_seed.py               | 260 ----------------
 backend/app/services/demo_data.py                 |  41 ---
 backend/app/services/membership_lifecycle.py      |  19 --
 backend/bot/onboarding.py                         |   2 -
 backend/scripts/clear_seeded_demo_transactions.py |  85 ++++++
 backend/tests/test_onboarding.py                  |   1 -
 backend/tests/test_phase12_bot_chrome.py          |   1 -
 backend/tests/test_phase16_demo_data.py           | 356 +---------------------
 backend/tests/test_phase9_members.py              |   2 +-
 backend/tests/test_quick_entry_parser.py          |  75 +++++
 frontend/src/api/demoData.ts                      |  59 ----
 frontend/src/pages/SettingsPage.tsx               |  51 ----
 16 files changed, 203 insertions(+), 829 deletions(-)
```

---

## RAW GIT STATUS

```
On branch fix/income-type-and-demo-data-removal
Changes not staged for commit:
	modified:   AGENTS.md
	deleted:    docs/context/cursor-prompt-phase-13.md
	modified:   docs/context/handoff.md

Untracked files:
	.claude/
	docs/app.log
	docs/bugs_screens/
	docs/context/cascade-keyword-review.md
	docs/context/cursor-prompt-bugfix-income-type-and-demo-data-removal.md
	docs/context/cursor-prompt-phase-16e-bugfix-tx-deeplink-and-delete-card.md
	docs/context/cursor-prompt-phase-16g-cascade-fallback-log.md
	docs/context/deploy-mvp2-vs-mvp1-notes.md
	docs/context/mini-prd-cascade-demo-protected-categories.md
	docs/context/mini-prd-cascade-fallback-log.md

no changes added to commit
```

(Unrelated dirty tree left untouched; not part of the three commits.)

---

## RAW BACKEND TESTS

### Baseline (before any commits on this branch)

```
3 failed, 512 passed, 1 warning in 26.53s
```

Failures (already on main):
- `test_cascade_fallback_log.py::...test_prefilter_miss_logs_even_when_model_limit_exhausted`
- `test_cascade_fallback_log.py::...test_prefilter_hit_writes_no_log_row`
- `test_cascade_fallback_log.py::...test_prefilter_disabled_logs_with_prefilter_disabled_reason`

### After Task 1 (`87aca28`)

```
3 failed, 516 passed, 1 warning in 28.62s
```

(+4 new parser tests; same 3 cascade failures)

### After Task 2 (`54867b5`)

```
4 failed, 515 passed, 1 warning in 29.49s
```

Same 3 cascade + new environmental failure:
- `test_wallets_categories.py::TestIncomeCategoriesApi::test_income_category_delete_returns_affected_count_and_hides_from_get`

Cause: test does unscoped `select(Transaction)`; after local soft-delete of demo rows (`is_deleted=True`), scalar can return a soft-deleted demo row. Not a product regression from the script.

### After Task 3 / final (`b5da2f7`)

```
4 failed, 511 passed, 1 warning in 26.23s
```

Same 4 failures. Pass count drop vs Task 1 is from deleted demo-feature tests in `test_phase16_demo_data.py` (expected).

---

## RAW FRONTEND TESTS

### Baseline

```
Test Files  42 passed (42)
Tests  244 passed (244)
```

### After Task 1

```
Test Files  42 passed (42)
Tests  244 passed (244)
```

### After Task 2

```
Test Files  42 passed (42)
Tests  244 passed (244)
```

### After Task 3 / final

```
Test Files  42 passed (42)
Tests  244 passed (244)
```

---

## ACCEPTANCE

### Task 1 — Bare income → expense
- [x] Rule added to `IMMUTABLE_PARSER_INSTRUCTIONS` (immutable/cached block only)
- [x] Coverage for `Kirim 500000 som` → income
- [x] Coverage for `kirim 500 ming` → income
- [x] Negative control `Chiqim 500000 som` → expense
- [x] `_PLAIN_AMOUNT_RE` / prefilter not touched
- [x] One commit

### Task 2 — One-off demo cleanup
- [x] Script uses soft-delete via existing mechanism (initially `clear_demo_transactions`; after Task 3 rewritten to `soft_delete_transaction` directly)
- [x] Iterates all `family_budget_id` with non-deleted `is_demo=True`
- [x] Localhost safety gate; ran against local/dev only
- [x] Counts reported
- [x] One commit

### Task 3 — Remove demo feature
- [x] Removed `seed_demo_operations` from onboarding and membership detach
- [x] Left `copy_seed_categories_only` / `copy_seed_wallets_only` / `copy_seed_data`
- [x] Deleted `demo_data` service, API routes, router registration
- [x] Removed demo seed helpers from `budget_seed.py`
- [x] Removed Settings clear-demo UI + `demoData.ts`
- [x] Tests updated/deleted
- [x] No schema migration / no `is_demo` column drop
- [x] One commit

---

## EXTRA — explicit answers

### 1. Exact wording added to `IMMUTABLE_PARSER_INSTRUCTIONS`

Verbatim (as concatenated in the string):

> Bare direction words set type even with no category match. Income markers (case-insensitive): kirim, приход, доход, получил, получила, заработал, заработала → type income. Expense markers: chiqim, расход, потратил, потратила, заплатил, заплатила → type expense. When an income marker is present, never default to expense.

### 2. Cleanup script result

| Field | Value |
|-------|--------|
| Script | `backend/scripts/clear_seeded_demo_transactions.py` |
| Host | `localhost` (local/dev — proceeded) |
| Transactions cleared | **67** |
| Family budgets affected | **3** |
| Idempotent re-run | 0 / 0 |

**Not run against production.** Production not configured in this workspace’s DATABASE_URL (host was localhost).

### 3. Remaining `is_demo` references (column not dropped)

Still present after Task 3:

| Location | Role |
|----------|------|
| `backend/app/models/transaction.py` | ORM column `is_demo` |
| `backend/alembic/versions/t0c1d2e3f4a5_transaction_is_demo.py` | Migration that added the column |
| `backend/scripts/clear_seeded_demo_transactions.py` | One-off cleanup queries filter `is_demo=True` |
| `backend/tests/test_phase16_demo_data.py` | Schema/default tests for the column only |

No product API, UI, or seed path reads/writes `is_demo` anymore (except the one-off cleanup script). PM decision needed for a future migration to drop the column.

---

## DEFERRED STUBBED OR DISABLED

None for this branch’s deliverables.

Environmental notes (not stubbed; pre-existing / shared-DB):
- 3 failing cascade-fallback-log tests (already failing on main before this branch)
- 1 wallets/categories test failing after local demo soft-delete due to unscoped `select(Transaction)` in the test

---

## MODEL ROSTER

| Role | Model |
|------|--------|
| Orchestrator | Cursor Grok 4.5 |
| Task 1 implementer | composer-2.5 |
| Task 2 implementer | composer-2.5 |
| Task 3 implementer | composer-2.5 |

No model substitution.

---

## QUESTIONS

1. **Prod cleanup:** local cleared 67 txns / 3 budgets. When ready, run the same script against prod only after confirming host gate (or temporarily allowing the prod host under your control). Confirm before any prod run.
2. **`is_demo` column:** drop via migration later, or leave indefinitely?
3. **Cascade fallback log failures on main** (3 tests) and the unscoped `select(Transaction)` test fragility — out of this branch’s scope; want a follow-up?

---

## Per-task worker notes (short)

### Task 1
- Files: `prompt.py`, `stub.py`, `test_quick_entry_parser.py`
- StubParser fixtures + prompt keyword assertions (no live Gemini call in CI)

### Task 2
- Added `backend/scripts/clear_seeded_demo_transactions.py`
- Safety gate: only `localhost` / `127.0.0.1` / `::1`

### Task 3
- Also removed detach-time card_uzs/card_usd fallback that existed only to guarantee wallets for demo seeding when personal wallets already existed; `copy_seed_wallets_only` still runs when the departing member has zero personal wallets
- Detach-with-personal-wallets test expectation updated: 1 wallet (personal only), not 5
