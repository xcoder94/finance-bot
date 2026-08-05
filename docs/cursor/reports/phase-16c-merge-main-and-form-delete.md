# Report — Phase 16c: merge `main` + in-form delete buttons

Branch: `mvp2/phase-16-cascade-demo-protected-support`  
Range: `32eceed` → `6f98f8d` (3 commits on this branch tip after Task 1 merge parents)  
Date: 2026-08-05  
Orchestrator: Cursor Grok 4.5  
Workers: `composer-2.5` only (implementation + review; no `-fast`, no substitution)

---

## Tests

| Moment | Backend (`pytest -q`) | Frontend (`npx vitest run`) |
|--------|------------------------|-----------------------------|
| This branch before Task 1 (`32eceed`) | **465 passed** | **38 files / 222 passed** |
| `main` before merge (`3b853e9`) | **446 passed** | **37 files / 205 passed** |
| After Task 1 merge (`3db4420`) | **499 passed** | **38 files / 222 passed** |
| After Task 2 feature (`571f0c1`) | **499 passed** | **40 files / 233 passed** |
| **Final (this report, `6f98f8d`)** | **499 passed**, 1 warning | **39 files / 235 passed** |

Counts did not drop below either side’s baseline after the merge. Frontend rose by **+13** tests for in-form delete (presence/absence + click wiring). Backend gain vs pre-merge branch tip is from phase-14b/15 suites brought in by `main`.

Disabled / stubbed / mocked introduced in this phase: **none**.

---

## Commits (this phase)

| SHA | Subject | Task |
|-----|---------|------|
| `3db4420` | Merge branch 'main' into mvp2/phase-16-cascade-demo-protected-support | 1 |
| `571f0c1` | feat(settings): add in-form delete for wallets and categories | 2 |
| `6f98f8d` | test(settings): add delete button click wiring tests | 2 (review fix) |

---

## Task 1 — merge `main` (voice + receipt photo onto phase-16) — DONE

**Why:** Branch forked from `main` at `97fd2d1` before `mvp2/phase-14b-and-15` landed. Voice and receipt-photo code were simply absent — not broken.

**Merge:** plain merge commit `3db4420` (parents `32eceed` + `3b853e9`). No rebase/squash.

### Conflict resolution (exactly 3 files)

| File | Resolution |
|------|------------|
| `backend/app/config.py` | Kept `main`: `SPEECH_*` removed; `RECEIPT_PHOTO_ENABLED` + `receipt_photo_enabled()` (default off). Phase-16 config elsewhere retained. |
| `backend/bot/main.py` | **Both** sides: support-relay router when `SUPPORT_CHAT_ID` set; receipt-photo router when `receipt_photo_enabled()`. |
| `backend/bot/quick_entry/handlers.py` | True merge: `main`’s shared `_process_parsed_response` / voice / receipt path **plus** phase-16 `try_prefilter()` inside `process_quick_entry_text` before the model call. |

### Sanity checks (code)

| Behavior | Result |
|----------|--------|
| Text quick entry hits cascade prefilter before model call | OK |
| Voice uses shared pipeline; prefilter remains text-only | OK |
| Receipt photo respects `RECEIPT_PHOTO_ENABLED` (default off) | OK |
| Support relay registers only when `SUPPORT_CHAT_ID` set | OK |

Review: **Approved** (spec ✅). Minor note: prompt’s old “464+1 known fail” baseline vs observed **465 passed** — harmless documentation inconsistency; merge itself clean.

---

## Task 2 — delete button inside edit forms — DONE

**PM decision:** design mock only shows swipe-to-delete for wallets / expense subcategories; PM chose to **also** add an explicit «Удалить» inside the open edit form. Deliberate, approved appearance deviation for *presence*; look still taken from the design system.

### Scope (exactly three)

1. `WalletFormSheet` — `mode === 'edit'`
2. `CategoryFormSheet` — `kind === 'income'`, `mode === 'edit'`
3. `CategoryFormSheet` — `kind === 'expense-subcategory'`, `mode === 'edit'`

**Out of scope (untouched):** expense *parent* categories — no edit form today (tap navigates to subcategories).

### Behavior

- Delete control only in edit mode (never create).
- Optional `onDelete` from parent; button shown iff edit + callback provided.
- Parents pass `onDelete` only when swipe delete would already be allowed:
  - Shared wallets → owner only; personal wallets → always (same as swipe).
  - Income / expense subcategory → owner only.
- Click sets the **same** `sheetState` as swipe → existing `EntityDeleteConfirmSheet` + existing copy/handlers. No second confirmation UI.
- Swipe-to-delete on list rows unchanged (additive).
- Label verbatim: **Удалить**.
- Style: existing `.form-sheet-danger-button` (`border: 1px solid var(--exp)`, outline danger, padding/radius matching design component library ~636–639), via `FormSheet` `danger` slot.

### Tests

- Presence in edit / absence in create / absence without `onDelete` for all three surfaces.
- Behavioral click: mock `FormSheet`, invoke danger `onClick`, assert `onDelete` called (same capture pattern as `notificationsSettingsShell.test.tsx`; no new test packages).
- Expense-subcategory parity with income cases.

Review: first pass **Issues** (Important: click→confirm only approximated by source-string wiring). Fix commit `6f98f8d` closed the gap. Re-review: **Approved** (spec ✅).

---

## Screenshots referenced

- `docs/bugs_screens/Pasted image.png` — wallet edit, no delete (before)
- `docs/bugs_screens/Pasted image (2).png` — income category edit, no delete (before)
- `docs/bugs_screens/Pasted image (3).png` — expense subcategory edit, no delete (before)

---

## Notes for PM

1. After this tip, one running app has phase-16 features **plus** voice + receipt photo from `main`. Receipt photo stays off until `RECEIPT_PHOTO_ENABLED` is set.
2. In-form «Удалить» is the approved design deviation; swipe remains the list mechanism.
3. Unrelated local dirty/untracked files (`AGENTS.md`, `docs/PRD.md`, `docs/context/*`, `docs/bugs_screens/*`, etc.) were **not** committed in this phase.
