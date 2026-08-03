# Phase 4 — History and Manual Forms Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Worker model:** `composer-2.5` only. Do not substitute.

**Goal:** Person opens History from Home (back returns Home), adds/edits own operations via MVP2 bottom-sheet forms matching design, with parent-only expense, transfer rate only when currencies differ, comment ≤200, and delete via confirmOp sheet.

**Architecture:** Keep `/history` route for Home entrance (Analytics `История` tab wiring stays Phase 5 stub note). Rebuild History list/empty/skeleton to design chips. Replace MVP1 full-page add/edit forms with modal bottom sheets (same routes OK: sheet overlays full viewport, no tabbar). Category picker is its own sheet. Backend: allow expense on parent categories; enforce comment max 200; expose `default_wallet_id` on `/me` for wallet prefills. No `Изменения` block (Phase 10). No type change on edit.

**Tech Stack:** Python/FastAPI/pytest; React/Vite/TypeScript/TelegramUI/Zustand/react-i18next; vitest (no new packages without asking).

## Global Constraints

- Spec: `docs/tasks/phase-04-history-forms.md` + PRD §17.3, §17.7, §5, §15.3 + customer standing rule (2026-08-03): **PRD = meaning, design = look/wording/placement**. Design wins on labels/copy/appearance; stop only if design breaks product logic.
- Design: `docs/design/Chontak MVP2.dc.html` — History empty/filled/skeleton; sheets `income`, `expense`, `catpick`, `transferSame`, `transferDiff`, `editClean`, `confirmOp`.
- Delete on edit sheet: secondary `Удалить запись` at bottom (design). Confirmation sheet `confirmOp` mandatory:
  - title: `Удалить запись?`
  - body: `Запись «{comment}» на {amount} {currency} удалится из истории и из аналитики. Отменить нельзя.`
  - If no comment: put **category name** in place of `{comment}` (income/expense category display name; for transfer use a sensible transfer title from existing display helpers — prefer destination/from labels already used in History rows).
  - danger: `Удалить запись`; **no primary button**.
- Forms are modal bottom sheets; primary save label `Сохранить`.
- Income/expense field order: amount (currency label from wallet, not selectable) → category → wallet (default prefilled) → date (today) → comment (≤200 with `N / 200` counter) → `Сохранить`.
- Category picker: parents expandable; may stop at parent; **«Без категории» never appears**.
- Expense: save with parent only allowed (no auto-create `Общее`).
- Transfer: same currency → no `Курс`; different → `Курс` + result line `100 $ → …` mandatory when rate shown.
- Type not editable on edit. No History bottom-menu tab. No floating `+`.
- Manual entry does not spend model-call / unparsed counters (API already separate from bot counters — do not wire counters).
- Transfer/exchange in History list: neutral colour, no minus (§5).
- Empty History: design copy `Операций за период нет` + hint `Смените месяц или сбросьте фильтр по категории.` (filter chip itself may be absent until Phase 5 — still show the empty card copy).
- Analytics History tab: **not built** this phase; report as unfinished pending Phase 5.
- Uzbek out of scope. Do not edit `AGENTS.md` / rewrite `docs/PRD.md`.
- Worker: `composer-2.5` only. Branch: `mvp2/phase-4-history-forms`.
- **Do not git commit** unless the orchestrator explicitly says to commit (user rule).
- Report before/after pytest + vitest; list stubs/finish-later.

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/services/transactions.py` | Allow parent expense categories |
| `backend/app/schemas/transactions.py` | `comment` max_length=200 |
| `backend/app/schemas/auth.py` + `api/v1/me.py` | `default_wallet_id` on `/me` |
| `backend/tests/test_transactions.py` | Parent expense OK; comment >200 → 422 |
| `backend/tests/test_phase3_budget_name.py` or new | `/me` default_wallet_id |
| `frontend/src/api/me.ts` | Map `defaultWalletId` |
| `frontend/src/pages/HistoryPage.tsx` + CSS | Design History; back to origin; open edit sheet |
| `frontend/src/components/forms/FormSheet.tsx` | Shared bottom sheet chrome |
| `frontend/src/components/forms/DeleteConfirmSheet.tsx` | confirmOp |
| `frontend/src/components/forms/CategoryPickerSheet.tsx` | expense/income catpick |
| `frontend/src/pages/Add*.tsx` / `Edit*.tsx` | Rebuild as sheets |
| `frontend/src/utils/formConfirmCopy.ts` | Build confirmOp body string |
| `frontend/src/i18n/locales/ru.json` | Verbatim design/PRD strings |
| `frontend/src/components/AppShell.tsx` / `NativeBackButton.tsx` | History back stack; form routes |
| Vitest helpers/tests | Navigation, comment limit, currency filter figures, transfer rate visibility helpers |

---

### Task 1: Backend — parent-only expense + comment ≤200

**Files:**
- Modify: `backend/app/services/transactions.py` — remove/reject the `parent_id is None → 400` check in `validate_expense_refs` (parent categories allowed). Keep 404 for missing/deleted.
- Modify: `backend/app/schemas/transactions.py` — on `IncomeCreate`, `ExpenseCreate`, `TransferCreate` (and thus updates): `comment: str | None = Field(default=None, max_length=200)`.
- Modify: `backend/tests/test_transactions.py` — flip `test_expense_rejects_top_level_category_with_400` to assert **201** and stored `expense_category_id == top.id`.
- Add tests: comment of length 201 → 422 on income/expense/transfer create; comment of length 200 → 201.

**Interfaces:**
- Produces: expense create/update accepts parent or subcategory id; comments longer than 200 rejected by schema.

- [ ] **Step 1:** Write/adjust failing tests (parent expense 201; comment 201 → 422).

- [ ] **Step 2:** Run focused pytest — FAIL.

- [ ] **Step 3:** Implement service + schema changes. Update any manual scripts that document “rejects top-level” if they would fail CI (scripts are not CI — skip unless broken).

- [ ] **Step 4:** Focused tests PASS; `cd backend && ./venv/bin/pytest -q` green.

- [ ] **Step 5:** Do **not** commit. Write report to `.superpowers/sdd/phase4-task-1-report.md`.

---

### Task 2: Backend + frontend — `default_wallet_id` on `/me`

**Files:**
- Modify: `backend/app/schemas/auth.py` `MeResponse` — add `default_wallet_id: uuid.UUID | None`
- Modify: `backend/app/api/v1/me.py` — return `user.default_wallet_id`
- Update `/me` tests that assert exact body keys
- Modify: `frontend/src/api/me.ts` + `authStore` — `defaultWalletId: string | null`
- Test: backend asserts field present; frontend `mapMeResponse` maps it

**Interfaces:**
- Produces: `AuthUser.defaultWalletId` for form prefills (fallback: first shared wallet if null).

- [ ] **Steps:** TDD backend then frontend mapping test → implement → suites green. No commit. Report `.superpowers/sdd/phase4-task-2-report.md`.

---

### Task 3: History screen — design empty/list + Home back + transfer colours

**Files:**
- Modify: `frontend/src/pages/HistoryPage.tsx`, `frontend/src/index.css` (history-*), `ru.json`
- Modify: `frontend/src/components/NativeBackButton.tsx` / entry navigation if needed so Home → History → back lands on Home (use `navigate('/history', { state: { from: 'home' } })` from Home; History back reads state or `navigate(-1)`).
- Home recent heading already navigates `/history` — set location state `from: 'home'`.

**Behaviour:**
1. Empty card matches design (title + hint verbatim).
2. Loading skeleton matches design list skeleton.
3. Filled rows: title, meta, amount colours — transfer/exchange neutral, no minus; expense red; income green.
4. Row tap opens edit flow (Task 6 may finish wiring; this task may still open existing edit route).
5. No fifth tab; no floating `+`.
6. Period month switch kept (meaning from existing History); visual polish toward design Analytics History list card.

**Vitest:** pure helper or nav test — opening History with `from: 'home'` resolves back target `/` (extract small `historyBackTarget(state)` helper).

- [ ] **Steps:** helper test → History UI + Home navigate state → vitest + build smoke. No commit. Report `.superpowers/sdd/phase4-task-3-report.md`.

---

### Task 4: Shared FormSheet + DeleteConfirmSheet (confirmOp)

**Files:**
- Create: `frontend/src/components/forms/FormSheet.tsx` — bottom sheet: handle, title, optional intro, fields slot, primary `Сохранить`, optional danger slot.
- Create: `frontend/src/components/forms/DeleteConfirmSheet.tsx` — confirmOp strings exactly; no primary; danger triggers delete callback.
- Create: `frontend/src/utils/formConfirmCopy.ts` + `.test.ts`:
  ```ts
  export function buildDeleteConfirmBody(args: {
    comment: string | null | undefined
    categoryLabel: string
    amount: number
    currency: 'UZS' | 'USD'
  }): string
  // → `Запись «${label}» на ${formattedAmount} ${currencyWord} удалится из истории и из аналитики. Отменить нельзя.`
  // currencyWord: UZS → `сум`, USD → `$` (match design “200 000 сум” / “100 $”)
  ```
- CSS under `index.css` for sheet tokens matching design (border-radius, padding, secondary danger style).

**Look:** match design sheet chrome; primary accent; danger outline/secondary as design.

- [ ] **Steps:** unit test body builder → implement sheets → vitest. No commit. Report `.superpowers/sdd/phase4-task-4-report.md`.

---

### Task 5: Category picker sheet + rebuild Income/Expense add forms

**Files:**
- Create: `frontend/src/components/forms/CategoryPickerSheet.tsx`
- Rewrite: `frontend/src/pages/AddIncomePage.tsx`, `AddExpensePage.tsx` to render as FormSheet overlays (route stays; page is sheet over dimmed backdrop; cancel/back closes via `navigate(-1)` or replace to origin).
- Remove auto-create `Общее` subcategory path entirely from expense add.
- Prefill wallet from `user.defaultWalletId` if present in wallets list, else first wallet.
- Amount currency label from selected wallet (`сум` / `$`), not a currency select.
- Date default today (Tashkent).
- Comment max 200; show `N / 200`; block save / reject over 200 in UI.
- Expense category row shows `Родитель · Подкатегория` when sub selected, or parent name alone.
- Picker intro (expense): `Можно остановиться на родителе — подкатегория необязательна.`
- Filter out any category named `Без категории` from picker lists (service value §15.3).
- Titles: `Новый доход` / `Новый расход` (design).
- Primary: `Сохранить`.
- On success: invalidate home/history caches; navigate back (no MVP1 success modal with “Добавить ещё” unless design shows it — **design has no success modal**; close sheet).

**Reuse:** existing POST endpoints; `transactionForm` digit helpers where useful.

- [ ] **Steps:** implement picker + both add forms; focused vitest for comment length helper / parent selection if extracted; frontend test + backend still green. No commit. Report `.superpowers/sdd/phase4-task-5-report.md`.

---

### Task 6: Transfer add form (same / different currency) + Edit sheets with delete

**Files:**
- Rewrite: `AddTransferPage.tsx` — fields `Откуда`, `Куда`, `Сумма`, optional `Курс` + result hint line, `Дата`, `Комментарий`; title `Перевод` or `Обмен` per design when currencies differ.
- Rewrite: `EditIncomePage.tsx`, `EditExpensePage.tsx`, `EditTransferPage.tsx` — same sheets as add + danger `Удалить запись` → opens DeleteConfirmSheet; on confirm DELETE API; no type switcher; **no `Изменения` block**.
- Wire History row / remove reliance on detail-modal delete as the only path: prefer edit sheet with delete (detail modal may remain for view or be simplified — if both exist, edit sheet must have delete; do not leave dead controls). Prefer: row opens edit sheet directly (design); detail modal can be removed from History path if it becomes redundant — if removed, ensure no broken imports.

**Transfer result line:** format like design `100 $ → 1 280 000 сум` using existing `transactionForm` rate helpers.

- [ ] **Steps:** implement; ensure same-currency hides rate; cross-currency shows rate+result; edit delete uses confirmOp. Tests for rate visibility helper. No commit. Report `.superpowers/sdd/phase4-task-6-report.md`.

---

### Task 7: Home actions + History wiring + i18n sweep + verification gate

**Files:**
- `HomePage.tsx` — action buttons still go to add routes (now sheets); recent heading passes `from: 'home'`; optional: make recent rows open edit (design on History; Home rows may stay non-clickable per phase 3 finish-later — if still non-clickable, OK and list under stubs).
- `ru.json` — all user-visible form/History strings match design (verbatim).
- Navigation test: `historyBackTarget` / mock state → `/`.
- Run full: `cd backend && ./venv/bin/pytest -q` and `cd frontend && npx vitest run --reporter=dot` and `npm run build`.
- Acceptance self-check against phase-04 §2 items 1,3–10 (item 2 Analytics deferred).

**Stubs to report:** Analytics `История` tab unfinished (Phase 5); `Изменения` absent (Phase 10); editing others’ shared ops (Phase 10).

- [ ] **Steps:** wire + verify + write `.superpowers/sdd/phase4-task-7-report.md` with before/after outputs and stub list. No commit.

---

## Self-review

1. Spec coverage: History Home entrance + back; forms field order; parent-only expense; catpicker; transfer rate states; edit+delete confirmOp; comment 200; empty History; transfer colours — tasks 1–7. Analytics entrance deferred explicitly.
2. Design wording for delete/confirm recorded in Global Constraints.
3. No History tab / no floating `+`.
4. Parent expense is product meaning from PRD §17.7 — API change required.
5. Placeholder scan: none intentional.
6. Commits deferred to human request.
