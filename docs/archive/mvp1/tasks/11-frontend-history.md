# Task 11 — Frontend: Transaction History

Depends on: Task 09 (`09-frontend-home.md` — done), Task 06
(`06-api-history-analytics.md` — done, backend confirmed sufficient,
no changes needed), Task 05 (`05-api-transactions.md` — done, `GET`/
`PATCH`/`DELETE /transactions/{id}` already implemented with
role-based `require_modify_permission`, confirmed sufficient for Part
2 of this task)
PRD reference: §4.5 (History)

## Goal

Replace the `PlaceholderPage` currently mounted at `/history` in
`AppShell.tsx` with a real History screen: period filter (month
selector or custom date range), per-currency income/expense totals for
the selected period, and a paginated list of transactions.

**This task is delivered in two parts, both living in this same task
file (not two separate task numbers):**
- **Part 1 (this prompt)**: read-only screen — filters, summary
  totals, list, pagination.
- **Part 2 (separate follow-up prompt, sent later)**: edit/delete a
  transaction directly from this screen, using the already-existing
  `GET`/`PATCH`/`DELETE /api/v1/transactions/{id}` endpoints. Do
  **not** build any edit/delete UI in Part 1 — out of scope until the
  Part 2 prompt is sent.

## Reference mockup

One screenshot is provided alongside this task file ("История
операций"). **Scope of the mockup**: it is the source of truth for
the **visual style of the list rows only** — colors (green/red/neutral
per row type), row layout (title + subtitle + author on the left,
amount + date on the right), typography, spacing, rounded-card
container. It is **not** the source of truth for the filter UI — the
filter behavior is fully specified below in this document, and where
the two disagree, this document wins. In particular, the mockup shows
the month selector and the "С"/"По" date fields visible at the same
time with live sync between them — **this is explicitly not what we're
building**; see "Period filter" below for the actual (tab-based)
design.

## Routing

In `AppShell.tsx`, replace:
```
<Route path="history" element={<PlaceholderPage titleKey="nav.history" />} />
```
with a new `HistoryPage` component. This route stays **nested inside
`AppLayout`** (keeps the Tabbar and the standard header), unlike the
Add Income/Expense/Transfer routes from Task 10.

## Period filter

Two tabs, rendered with the same `SegmentedControl` component already
used for the currency toggle on Home (Task 09) for visual consistency:
**"Месяц"** and **"Диапазон"**. Only one tab's filter is active at a
time; switching tabs does not merge or sync state between them.

### "Месяц" tab (default active tab on first load)
Identical UX to Home's month selector: `‹ Июнь 2026 ›`, defaults to
the current month. Produces `date_from` = first day of month 00:00:00,
`date_to` = last day of month 23:59:59.999 — reuse the exact logic of
`monthDateRange()` from `frontend/src/api/home.ts` (UTC-based day
boundaries, same convention already used for Home's summary fetch —
do not introduce a second, different date-boundary convention here).

### "Диапазон" tab
Two fields, "С" and "По", using the **same masked `ДД.ММ.ГГГГ` text
input pattern** as the date/time field in Task 10's
`MaskedDateTimeInput` — but date-only, no time portion, no comma/HH:MM
suffix. Do not use a native `<input type="date">` (rejected for the
same reason native `datetime-local` was rejected in Task 10: display
format is locale-dependent, not controlled by the page).
- On first switch to this tab (or on initial mount if it becomes the
  active tab later), pre-fill both fields with the current month's
  first/last day (same values the "Месяц" tab would produce) — this is
  a one-time default, not a live sync. After that, editing either
  field only affects that field; switching back to "Месяц" and forward
  to "Диапазон" again does **not** reset user edits.
  produces `date_from` = "С" date at 00:00:00, `date_to` = "По" date at
  23:59:59.999, same UTC-boundary convention as above.
- Validate both fields the same way as Task 10's date field (real
  calendar date, inline error on blur/submit if invalid). If `date_from
  > date_to`, show an inline error and do not fetch (mirrors the
  backend's own `422` check in `history.py`, but catch it client-side
  first for a clean UX).

## Data fetching

Two backend calls per filter change, both already fully sufficient —
no backend changes:
- `GET /api/v1/analytics/summary?date_from&date_to` — reuse as-is,
  it already accepts arbitrary `date_from`/`date_to` (not limited to a
  calendar month). Add a typed fetch helper if one doesn't already
  fit; `fetchSummary` in `home.ts` is month-shaped, so add a
  lower-level `fetchSummaryForRange(dateFrom, dateTo)` (or refactor
  `fetchSummary` to call it) in a new `frontend/src/api/history.ts`,
  reusing the existing `SummaryResponse`/`PerCurrencySummary` types
  from `home.ts` (import, don't redefine).
- `GET /api/v1/transactions/history?date_from&date_to&limit&offset` —
  add `fetchHistoryPage(dateFrom, dateTo, limit, offset)` in the same
  new `frontend/src/api/history.ts`, reusing `HistoryItem`/
  `HistoryResponse` types from `home.ts`.

Both calls re-fire whenever the active filter's resolved `date_from`/
`date_to` changes (tab switch, month navigation, or a valid edit to
the range fields). Use the same loading/error block pattern as Home
(`BlockError`, `Spinner`, retry button) — no new pattern needed.

## Summary block (totals)

Show income/expense totals for **both currencies at once**, no
primary-currency toggle (unlike Home) — reuse `PerCurrencySummary`
entries for `UZS` and `USD` from the `summary` response. Two metric
cards per currency (Income green, Expense red), grouped so it's clear
which pair belongs to which currency (e.g. a small `UZS` / `USD` label
above each pair, or two side-by-side card groups) — exact layout is an
implementation detail, keep it visually consistent with Home's
existing metric-card styling (`home-metric-card` classes / patterns),
new CSS classes are fine if needed.

## Transaction list

Rendered as a single vertical list (reuse the rounded-card container
style from the mockup / Home's `home-recent__list` pattern), one row
per `HistoryItem`. Each row:

**Left side, top to bottom:**
1. **Title** (bold, colored):
   - `income` → `income_category_name`, green
   - `expense` → `expense_subcategory_name`, red
   - `transfer` with `currency === to_currency` → `t('history.transfer')`
     ("Перевод"), neutral color
   - `transfer` with `currency !== to_currency` → `t('history.exchange')`
     ("Обмен валюты"), neutral color
2. **Subtitle** (regular weight):
   - `income` → `t('home.income')` ("Доход") — generic type label
   - `expense` → `expense_category_name` (the **parent** category, not
     the subcategory — subcategory is already the title)
   - `transfer`/exchange → `` `${wallet_name} → ${to_wallet_name}` ``
3. **Author** (small, muted) — `created_by`, shown **only when
   present**. The backend already omits this field entirely when the
   Family Budget has a single member (see `should_include_created_by`
   in `history.py`) — the frontend just renders it conditionally on
   `item.created_by` being non-null, no separate logic needed.
4. **Comment** (small, muted, below author) — `item.comment`, shown
   **only when non-empty**. Not present in the mockup screenshot
   (that test data had no comments) but is a required PRD §4.5 column.

**Right side, top to bottom:**
1. **Amount** — `income` shown with `+` prefix and green;
   `expense` shown with `-` prefix and red; `transfer`/exchange shown
   with no sign, neutral color. Format with `formatCurrency(amount,
   currency)`, same helper already used on Home. Reuse the existing
   `formatSignedTransactionAmount`-style logic from `HomePage.tsx`
   (extract into a shared util if convenient, or duplicate minimally —
   your call).
2. **Date/time** — same `DD.MM.YYYY HH:MM` formatting already used on
   Home (`formatTransactionDateTime` in `HomePage.tsx` — reuse or
   extract, don't reimplement differently).

## Pagination

"Показать ещё" button below the list (not infinite scroll, not a
numbered pager). Initial load: `limit=50, offset=0`. On click: fetch
next page with `offset += limit`, **append** to the existing list (do
not replace). Hide the button once `items.length >= total_count`. Any
filter change (tab switch, month navigation, valid range edit) resets
the list and `offset` back to 0 and re-fetches from scratch.

## i18n

New `history.*` keys in `ru.json`/`uz.json`: screen title ("История
операций"), tab labels ("Месяц", "Диапазон"), field labels ("С",
"По"), `history.transfer` ("Перевод"), `history.exchange` ("Обмен
валюты"), "Показать ещё", empty-state text (reuse `home.noTransactions`
wording/pattern if it fits), load-error text (reuse `home.loadError`
pattern). Follow the existing key-naming convention (`home.*`,
`addTransaction.*`).

## Out of scope for this task (Part 1)

- Editing or deleting a transaction from History (Part 2 — separate
  follow-up prompt using this same task file, sent later; endpoints
  already exist and are confirmed sufficient, see "Depends on" above).
- Any filter beyond period (no type/wallet/category/currency filter —
  explicitly decided against).
- Any backend change — `analytics/summary` and `transactions/history`
  are already sufficient as-is.
- A currency toggle on the summary block (both currencies always shown
  together).
- Tapping a row for details/navigation (no row click behavior at all
  in Part 1).

## Acceptance criteria (Part 1)

- [ ] `/history` renders the new `HistoryPage` inside `AppLayout`
      (Tabbar visible, standard header), replacing the placeholder.
- [ ] "Месяц" tab is active by default, shows the current month, and
      behaves identically to Home's month selector (‹ / › navigation).
- [ ] "Диапазон" tab shows masked `ДД.ММ.ГГГГ` "С"/"По" fields,
      pre-filled with the current month's boundaries on first switch;
      editing them is independent of the "Месяц" tab and persists
      across tab switches; invalid dates or `С` > `По` show an inline
      error and block fetching.
- [ ] Switching tabs or navigating months/editing a valid range
      re-fetches both summary and the (reset) transaction list.
- [ ] Summary block shows Income/Expense for **both** UZS and USD
      simultaneously, correctly colored, for the currently active
      filter's period.
- [ ] List rows show correct title/subtitle/author/comment/amount/date
      per the rules above, for all three transaction types, including
      the "Перевод" vs "Обмен валюты" distinction based on
      same-vs-different wallet currency.
- [ ] Author line appears only when the API response includes
      `created_by` (i.e., only in a multi-member Family Budget);
      comment line appears only when `comment` is non-empty.
- [ ] "Показать ещё" loads the next page and appends (doesn't replace)
      results; disappears once all matching transactions are loaded.
- [ ] Empty state (no transactions in the selected period) and network
      error states (with retry) are handled, same visual pattern as
      Home.
- [ ] No TypeScript / build errors; `npm run dev` runs clean; `npm run
      lint` and `npm run build` pass.

## Verification (Part 1)

Manual, in browser, step by step:

1. Open `/history` from the Tabbar — confirm it loads with "Месяц"
   tab active, current month, Tabbar still visible.
2. Navigate months with ‹/› — confirm summary totals and list both
   update for each month with no manual reload, and offset resets to 0.
3. Switch to "Диапазон" — confirm fields pre-filled with current
   month's first/last day. Change "С" to an earlier date — confirm
   summary and list update to the wider range.
4. Switch back to "Месяц" then back to "Диапазон" — confirm the
   manually-edited range values are preserved, not reset.
5. Enter an invalid date (e.g. 31.02.2026) or set "С" after "По" —
   confirm inline error, no request sent.
6. Confirm at least one income, one expense, one same-currency
   transfer, and one cross-currency transfer are visible with correct
   colors, titles ("Перевод" vs "Обмен валюты"), subtitles, and signed
   amounts.
7. Add a comment to a test transaction (via Add Expense/Income form or
   DB) and confirm it appears as a muted line in its History row; find
   a transaction with no comment and confirm no empty line is shown.
8. If the active test Family Budget has 2+ members: confirm author
   name shown on each row. If only 1 member: confirm no author line
   anywhere (matches backend `should_include_created_by` behavior —
   may require temporarily testing with the Owner+Member seed data).
9. Click "Показать ещё" (requires 50+ transactions in the period, or
   temporarily test with a smaller effective page size if easier) —
   confirm next page appends, button disappears once exhausted.
10. Pick a period with zero transactions — confirm empty-state message,
    no crash.
11. Stop the backend, reload `/history` — confirm error block + retry
    on both summary and list sections independently; restart backend,
    click retry on each — confirm both recover.

## Part 2 — Edit / Delete a transaction from History

Backend requires **no changes** for this part: `GET/PATCH/DELETE
/api/v1/transactions/{id}` (`backend/app/api/v1/transactions.py`)
already exists, already enforces `require_modify_permission`
(Owner — any transaction; Member — only their own, via
`created_by_user_id`), and `TransactionResponse` already includes
`created_by_user_id`. `GET /api/v1/me` already returns the current
user's own `id`. `IncomeUpdate`/`ExpenseUpdate`/`TransferUpdate` are
identical to their `Create` counterparts (`extra="forbid"`, same
required fields) — **PATCH is a full replace, not a partial update**:
the edit form must submit every field, not just changed ones, exactly
like the Add forms.

### Trigger: tap a row

Tapping anywhere on a `HistoryItem` row opens a detail modal (reuse
`Modal` from `@telegram-apps/telegram-ui`, same component family as
`TransactionSuccessModal` from Task 10). On tap:
1. Call `GET /api/v1/transactions/{id}` to get the full record
   (needed for `wallet_id`/`income_category_id`/`expense_category_id`/
   `to_wallet_id`/`rate`/`created_by_user_id` — none of which are in
   the list's `HistoryItem`, which only has display names).
2. While loading, show a loading state inside the modal (`Spinner`),
   not a full-page loader.
3. On success, show read-only details: same title/subtitle logic as
   the list row (income/expense/transfer, "Перевод" vs "Обмен
   валюты"), amount, date/time, wallet name(s), comment (if any),
   author (if `created_by` present on the original list item).
4. Determine edit/delete permission client-side: current user's `id`
   (from the already-fetched `/me` response — extend `authStore`/the
   auth bootstrap flow to expose it if it isn't already stored) is
   compared against `created_by_user_id` from the fetch in step 1.
   Show **"Редактировать"** and **"Удалить"** buttons only if the
   current user's role is `owner`, **or** `created_by_user_id` matches
   the current user's own `id`. Otherwise show only a close button —
   no error, no disabled-greyed buttons, they simply aren't rendered.
5. On `GET` failure, show an inline error + retry inside the modal
   (same `BlockError` pattern used elsewhere), not a full navigation
   away.

### Edit

"Редактировать" navigates to one of three new top-level routes
(outside `AppLayout`, no Tabbar — same pattern as Task 10's Add
routes): `/edit-income/:id`, `/edit-expense/:id`, `/edit-transfer/:id`
— picked based on the transaction's `type` from the step-1 fetch.

Each edit page is structurally the Task 10 Add page for that type,
adapted to:
- Pre-fill every field from the fetched `TransactionResponse` (date/
  time converted to the masked display format; amount/rate as raw
  digit strings; wallet/category selects set to the existing IDs; for
  Expense, derive and pre-select both the parent category and the
  subcategory from `expense_category_id` using the same
  `getTopLevelCategories`/`getSubcategories` helpers already in
  `AddExpensePage.tsx`).
- Submit via `PATCH /api/v1/transactions/{id}` instead of `POST
  .../transactions/{income|expense|transfer}`, sending the full field
  set (not a diff).
- On success: navigate straight to `/history` — **no success modal**,
  unlike the Add forms (no "Добавить ещё" makes sense here, and no
  extra confirmation step was wanted). The History screen must show
  the updated data on arrival (same "no special code needed, remount
  refetches" pattern as Task 10's Home-refetch — but verify manually
  in-browser, don't assume from code alone).
- On failure: same inline error + "Повторить" pattern as the Add
  forms.
- "Отменить" button navigates back (browser back, or directly to
  `/history` — either is fine, pick whichever is simpler given the
  existing routing setup).
- Reuse all existing field components as-is (`MaskedDateTimeInput`,
  `LimitedDigitInput`, `TransactionReceiveRow`, live calculator for
  cross-currency transfers, same validation rules) — no new form
  components, this is the same shared `TransactionFormShared.tsx`.

### Delete

"Удалить" in the detail modal opens a **second, separate confirmation
step** (either a nested confirm modal or the same modal switching to a
confirm view — implementation detail) with the text "Удалить эту
операцию?" and two buttons: "Отменить" (returns to the detail view)
and "Удалить" (calls `DELETE /api/v1/transactions/{id}`). On success:
close all modals and refresh the History list (re-fetch, staying on
`/history`, no navigation). On failure: inline error + retry within
the confirmation step, don't silently close.

### Out of scope for Part 2

- Any backend change (confirmed unnecessary above).
- Editing/deleting from anywhere other than the History screen (e.g.,
  no edit/delete entry point added to Home's Recent Transactions list
  — out of scope unless a future task asks for it explicitly).
- Bulk edit/delete, undo-after-delete, or any restore mechanism.
- Changing `created_by_user_id` on edit (backend already keeps it
  fixed to the original creator regardless of who edits, per
  `require_modify_permission` design in Task 05 — not this task's
  concern).

### Acceptance criteria (Part 2)

- [ ] Tapping a History row opens a detail modal, fetching full
      transaction data via `GET /transactions/{id}`; loading and error
      states handled within the modal.
- [ ] Edit/Delete buttons appear only when the current user is Owner
      or is the transaction's own creator; otherwise only a close
      button is shown — verified with both an Owner and a Member test
      account, on both own and others' transactions.
- [ ] "Редактировать" navigates to the correct `/edit-{type}/:id`
      route with every field correctly pre-filled from existing data,
      including correct parent-category + subcategory pre-selection
      for expenses.
- [ ] Saving an edit calls `PATCH` with the full field set, navigates
      to `/history` on success, and the updated values are visible
      there without a manual reload.
- [ ] Saving an edit with invalid data shows the same inline
      validation as the Add forms; a failed `PATCH` request shows
      inline error + retry.
- [ ] "Удалить" requires a second confirmation step before the actual
      `DELETE` call; confirming removes the transaction and the
      History list reflects it immediately; a failed `DELETE` shows
      inline error + retry, doesn't silently fail.
- [ ] No TypeScript / build errors; `npm run lint` and `npm run build`
      pass.

### Verification (Part 2)

Manual, in browser, step by step:

1. As Owner: tap several rows of different types (income, expense,
   same-currency transfer, cross-currency transfer) — confirm correct
   read-only details in each modal, correct "Перевод"/"Обмен валюты"
   distinction, Edit/Delete buttons visible.
2. As Owner, edit an income transaction — confirm all fields
   pre-filled correctly, change the amount and category, save, confirm
   navigation to `/history` with the new values visible.
3. As Owner, edit an expense transaction — confirm both parent
   category and subcategory are correctly pre-selected; change the
   subcategory, save, confirm it sticks.
4. As Owner, edit a cross-currency transfer — confirm rate field and
   live-calculator result appear pre-filled and still work live on
   edit.
5. As Owner, delete a transaction — confirm the confirmation step
   appears, "Отменить" returns to details without deleting, "Удалить"
   removes it and it's gone from the list on `/history`.
6. Switch to a Member test account: tap a transaction created by
   someone else — confirm no Edit/Delete buttons, only close. Tap a
   transaction the Member created themself — confirm Edit/Delete
   buttons do appear and work.
7. Try editing with invalid data (e.g. clear the amount) — confirm
   inline validation blocks submit, no request sent.
8. Stop the backend, attempt an edit save and a delete — confirm
   inline errors + retry in both cases; restart backend, retry —
   confirm both succeed.

## Addendum — Home recent-transactions list: apply "Перевод" vs "Обмен валюты"

**Found during final review, not implemented in Part 1.** The very
first architecture decision in this task ("Как отличать «Перевод» от
«Обмена валюты» в UI") explicitly covered **both** Home's Recent
Transactions list and the History screen — confirmed by the user
before Task 11 was scoped. Part 1 only applied it to
`HistoryPage.tsx`; `HomePage.tsx` (Task 09) still shows the generic,
currency-blind `t('home.transfer')` ("Перевод") for every transfer
row, both in the title (`getTransactionCategoryLabel`) and the
subtitle (`getTransactionTypeLabel`). This is a leftover gap in the
already-agreed Task 11 scope, not a new request — fix it as part of
this task, not as an unrelated Task 09 patch.

### What to change

In `frontend/src/pages/HomePage.tsx`:
- `getTransactionCategoryLabel` (used for the row **title**): for
  `type === 'transfer'`, instead of always returning the generic
  `transferLabel` param, return `t('history.exchange')` when
  `item.currency !== item.to_currency`, otherwise `t('history.transfer')`
  — reuse the existing `history.transfer`/`history.exchange` i18n keys
  added in Part 1 (do not duplicate them under a new `home.*` key).
- `getTransactionTypeLabel` (used for the row **subtitle**): apply the
  exact same same-vs-different-currency logic for `type === 'transfer'`
  (today it also always returns the generic `labels.transfer`). Yes,
  this means title and subtitle will show the same word for transfer
  rows on Home — that mirrors the current duplicate-text design
  already in place today (title and subtitle already both say
  "Перевод" for every transfer row before this fix; this fix only
  makes both consistently reflect the currency-based distinction, it
  does not redesign Home's row layout).
- Do not touch anything else in `HomePage.tsx` — no layout changes, no
  new fields, income/expense rows unaffected.

### Acceptance criteria (Addendum)

- [x] On Home's Recent Transactions list, a same-currency transfer
      shows "Перевод" in both title and subtitle.
- [x] A cross-currency transfer shows "Обмен валюты" in both title and
      subtitle.
- [x] Income and expense rows on Home are visually unchanged.
- [x] No TypeScript / build errors; `npm run lint` and `npm run build`
      pass.

### Verification (Addendum)

1. On Home, with at least one same-currency transfer and one
   cross-currency transfer among the 3 most recent transactions,
   confirm the correct label appears on each.
2. Confirm income/expense rows are unchanged from before this fix.

## Changelog

- **2026-07-20**: Part 1 implemented and verified. **Routing**
  (`AppShell.tsx`): `/history` now renders `HistoryPage` inside
  `AppLayout` (Tabbar stays visible), replacing the placeholder.
  **API layer** (`frontend/src/api/history.ts`): `fetchSummaryForRange`
  and `fetchHistoryPage`, reusing `HistoryItem`/`HistoryResponse`/
  `SummaryResponse` types from `home.ts`; `monthDateRange` exported
  from `home.ts` for reuse. **Page** (`frontend/src/pages/
  HistoryPage.tsx`): period filter as two `SegmentedControl` tabs
  ("Месяц" / "Диапазон"), month tab reusing Home's `‹ Month ›`
  navigation, range tab with date-only masked `ДД.ММ.ГГГГ` inputs
  (new `formatDateDigits`/`isoDateToMaskedDate`/`isValidMaskedDate`/
  `maskedDateToUtcStartIso`/`maskedDateToUtcEndIso` helpers added to
  `transactionForm.ts`), one-time default-then-independent range
  values, inline validation (invalid date, `С` > `По`). Dual-currency
  (UZS + USD simultaneously, no toggle) summary cards reusing
  `analytics/summary`. Transaction list with title/subtitle rules
  (including "Перевод" vs "Обмен валюты" based on same-vs-different
  wallet currency), conditional author (`created_by`) and comment
  lines, signed/colored amounts. "Показать ещё" pagination
  (`limit=50`, appends, resets to offset 0 on any filter change).
  Independent `BlockError`/retry for summary vs list sections,
  confirmed working correctly when the backend is stopped mid-session
  (full-page reload during backend downtime instead hits the
  earlier, already-existing Task 07 auth-bootstrap network-error
  screen — expected, not a Task 11 concern). **i18n**: `history.*`
  keys in `ru.json`/`uz.json`. **Styles** (`index.css`):
  history-specific layout. `npm run lint` and `npm run build` pass.
  One observation during verification (not a code issue): a dev/test
  Owner user with empty `first_name`/`username` in the `users` table
  renders as `"Unknown"` author — this is existing backend fallback
  logic (`history_analytics.py`, `get_history`), correctly surfaced by
  the frontend; a data/seed issue in the local dev DB, not a bug in
  this task.

*(Part 2 changelog entry to be added after edit/delete is implemented
and verified.)*

- **2026-07-20 (addendum)**: `HomePage.tsx` — Recent Transactions
  transfer rows now use `history.transfer` / `history.exchange` based on
  `item.currency !== item.to_currency` in both title
  (`getTransactionCategoryLabel`) and subtitle (`getTransactionTypeLabel`),
  matching History screen logic. No layout or i18n changes.
