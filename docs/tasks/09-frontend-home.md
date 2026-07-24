# Task 09 — Frontend: Home Screen

Depends on: Task 07 (`07-frontend-shell.md` — done), Task 06
(`06-api-history-analytics.md` — done), Task 08
(`08-api-wallet-balances.md` — done)
PRD reference: §4.1 (updated 2026-07-19 — see PRD §12/§13 changelog)

## Goal

Replace the Home `PlaceholderPage` (Task 07) with real content: month
selector, primary-currency toggle that fully hides the non-selected
currency's Income/Expense/Balance numbers, quick-action buttons (disabled
— forms don't exist until Task 10), and a "recent transactions" block
that is NOT filtered by currency.

## Reference mockup

A visual reference screenshot is provided alongside this task file (see
attached image / Cursor context). Match its layout, spacing, card style,
and color usage as closely as practical with TelegramUI components — it
is the source of truth for visual structure, this document is the source
of truth for data/behavior rules. Where they conflict, this document
wins; ask before guessing.

## Data sources (3 independent calls, per-block loading/error state)

1. `GET /api/v1/analytics/summary?date_from=<month start>&date_to=<month end>`
   — income/expense for the selected month. `by_currency` only contains
   currencies with activity in range — see "by_currency lookup" below.
2. `GET /api/v1/analytics/wallet-balances` — no params, all-time, fetched
   once on mount, **not refetched on month change**.
3. `GET /api/v1/transactions/history?date_from=<far past>&date_to=<now>&limit=3&offset=0`
   — sorted `transaction_date DESC` server-side (Task 06). Fixed date
   range, not derived from `selectedMonth` — fetched once on mount, same
   as `wallet-balances`, **not refetched on month change**.

Each of the 3 calls has independent loading/error state — **per-block
degradation**: if one fails, only that block shows an inline error +
"Retry" button; the other two render normally.

### `by_currency` lookup (unchanged from previous revision)

`summary`'s `by_currency` only includes currencies with activity in the
selected month — it is not a fixed two-item list. Always look up an
entry by its `currency` field, never by array index. If the currently
selected primary currency has no entry, treat it as
`{ income: 0, expense: 0 }`.

## State (local to HomePage, `useState` — no new Zustand slice)

- `selectedMonth` — `{ year, month }`, defaults to current month.
- `primaryCurrency` — `'UZS' | 'USD'`, defaults to `'UZS'`. Not
  persisted anywhere — resets to `'UZS'` on every page reload, same
  pattern as the Task 07 language switcher.

## Layout (top to bottom, per the reference screenshot)

1. **Page title** — "Мои финансы" (or the existing i18n key used for the
   Home nav label, whichever is already established — check
   `ru.json`/`uz.json` from Task 07 before adding a new key). If
   `AppShell` already renders a page title in its own header for other
   routes, follow that existing pattern instead of a redundant
   in-content title — check `AppShell.tsx` / other pages (e.g.
   `SettingsPage`) for the established convention before deciding.
2. **Month selector** — `‹ Июль 2026 ›` style: circular/pill arrow
   buttons flanking the month label, one month per click. No jump-to-date
   picker.
3. **Primary currency toggle** — full-width pill-style `SegmentedControl`
   with two segments, `UZS` / `USD`, placed below the month selector.
4. **Summary — two side-by-side cards + one full-width card below them**,
   all showing **only the selected `primaryCurrency`'s numbers** — the
   other currency is not shown anywhere in this section, not even
   smaller (this is the behavior change from the previous revision):
   - Left card: "Доход" (Income), value in green.
   - Right card: "Расход" (Expense), value in red.
   - Full-width card below: "Остаток" (Balance), value in neutral/dark
     color (not green/red — only Income/Expense are colored, Balance is
     not "earned" or "spent").
   - Income/Expense come from the `summary` call for `primaryCurrency`
     (via the `by_currency` lookup rule above), scoped to `selectedMonth`.
   - Balance comes from the `wallet-balances` call for `primaryCurrency`
     — always all-time, does not change when `selectedMonth` changes.
   - Empty month: Income/Expense render as `0` (not blank, not hidden);
     Balance still shows its real all-time value.
   - Switching the toggle re-renders this section instantly with the
     other currency's numbers — no refetch needed, both currencies'
     data are already in memory from the existing fetches.
5. **Quick-action buttons** — three circular icon buttons in a
   horizontal row, each with a short label below the circle (per
   reference: green circle "+"/"Доход", red circle "−"/"Расход", gray
   circle "⇄"/"Перевод"). They remain **functionally disabled** — no
   `onClick`, no routes, no navigation (Task 10 scope) — but are NOT
   visually greyed out; they render in their full color per the
   reference image, since that's the visual style being matched. Clicking
   must be a silent no-op (no console errors, no navigation).
6. **Recent transactions block** — up to 3 items from the `history`
   call, **never filtered by `primaryCurrency`** — shows the most recent
   transactions across all currencies, matching what History would show:
   - Each row: category/title + date on the left, amount (with its own
     currency, colored: Expense red, Income green, Transfer neutral) on
     the right.
   - Category/title text: `income_category_name` for income,
     `expense_subcategory_name` for expense, literal "Перевод" (i18n:
     `home.transfer`) for transfers. A small subtitle under it can show
     the type label (e.g. "Доход"), per the reference image.
   - No comment, no author shown (out of scope for this compact view).
   - Empty state (0 items returned — truly zero transactions ever, not
     just zero in the selected month, since this call isn't month-scoped):
     placeholder text, e.g. "Пока нет операций".

## Number formatting

- Thousands separator: `1 234 567` (space-separated).
- USD: `$` prefix, e.g. `$350`.
- UZS: `UZS` suffix, e.g. `1 234 567 UZS`.
- Shared helper `frontend/src/utils/formatCurrency.ts` (already exists
  from the previous revision) — reused as-is, no changes needed here.

## Out of scope for this task

- Add Income/Expense/Transfer forms (Task 10) — buttons are disabled
  stubs only (functionally — see layout item 5 for the visual exception).
- "Recent transactions" navigating anywhere on tap (no click handler).
- Persisting `primaryCurrency` (client-only, resets on reload).
- A currency filter on Recent Transactions, History, or Analytics — none
  exists anywhere in the app; the toggle only affects the Home summary
  block (PRD §4.1, updated 2026-07-19).
- Placing the currency toggle in the AppShell header slot (unless that's
  the established convention discovered in layout item 1 — if so, follow
  it; otherwise keep it in-content as before).
- Any change to backend endpoints.

## Acceptance criteria

- [x] Home renders real data: summary (income/expense for the selected
      primary currency, scoped to selected month), balance (for the
      selected primary currency, all-time), up to 3 recent transactions
      across all currencies
- [x] Month selector arrows move one month at a time; only the summary
      block (income/expense) refetches on month change; wallet-balances
      and recent-transactions do NOT refetch (both fetched once on mount)
- [x] Primary currency toggle **fully hides** the non-selected currency's
      Income/Expense/Balance numbers — switching shows only the selected
      currency's data in that block, instantly, no refetch; resets to
      UZS on page reload
- [x] Recent transactions are unaffected by the primary currency toggle
      — always show the same 3 most recent transactions regardless of
      which currency is selected
- [x] Add Income/Expense/Transfer buttons render in full color per the
      reference image but are functionally inert — no navigation, no
      console errors on click
- [x] Recent transactions show category/title, date, amount (correct
      color per type, in that transaction's own currency) — no comment,
      no author
- [x] `summary`'s `by_currency` is looked up by `currency` field, never
      by array index; a missing currency renders as `0`/`0`
- [x] Empty month: income/expense show 0 for the selected currency;
      balance still shows its correct all-time value; recent-transactions
      empty state shows placeholder text only if there are truly zero
      transactions ever
- [x] Each of the 3 data blocks has independent loading and error state;
      a failure in one does not block the other two from rendering
- [x] Numbers formatted with space-separated thousands; `$` prefix for
      USD, `UZS` suffix for UZS
- [x] Layout visually matches the reference screenshot: month selector,
      currency toggle, Income/Expense side-by-side cards + Balance card
      below, three circular quick-action buttons in a row, recent
      transactions list
- [x] No TypeScript / build errors; `npm run dev` runs clean

## Verification

Manual, in browser, step by step:

1. Open Home as Owner (dev auth) — confirm layout matches the reference
   screenshot (month selector, currency toggle, two cards + balance card,
   three round action buttons, recent transactions list).
2. Confirm Income/Expense/Balance show data for `UZS` (default) only —
   no USD numbers visible anywhere in that block.
3. Toggle to `USD` — confirm Income/Expense/Balance switch instantly to
   USD-only numbers (no loading spinner, no network request — open
   Network tab to confirm no new request fires on toggle).
4. Confirm recent transactions list is unchanged after toggling currency
   — same 3 items, same amounts/currencies as before the toggle.
5. Click month arrows — confirm the Income/Expense values update;
   confirm Balance does NOT change; confirm recent-transactions does NOT
   change; confirm no new request to `/transactions/history` fires
   (Network tab).
6. Reload the page — confirm primary currency resets to UZS.
7. Click each quick-action button — confirm nothing happens, no console
   errors.
8. Navigate to a month with zero transactions in the selected currency —
   confirm Income/Expense show 0; Balance still shows the correct
   all-time number.
9. Stop the backend server, reload — confirm each of the 3 blocks shows
   its own inline error + retry. Restart the backend, click each block's
   retry — confirm it recovers independently.

## Changelog

- **2026-07-19**: Task 09 implemented. Replaced Home `PlaceholderPage` with
  `HomePage` (`AppShell.tsx` route only; shell header hidden on `/` so
  Home shows a single in-content title — other routes still use the
  global `app.title` header, same as before). **API layer**
  (`frontend/src/api/home.ts`): typed fetch helpers for
  `GET /api/v1/analytics/summary`, `GET /api/v1/analytics/wallet-balances`,
  and `GET /api/v1/transactions/history` (response types match
  `app/schemas/history_analytics.py`), all using `getAuthHeader()`.
  **Formatting** (`frontend/src/utils/formatCurrency.ts`): shared
  space-separated thousands; `$` prefix for USD, `UZS` suffix for UZS.
  **HomePage** (`frontend/src/pages/HomePage.tsx`): layout matched to the
  reference mockup — in-content title (`home.title`), pill month selector,
  full-width currency toggle, two side-by-side Income (green) / Expense (red)
  cards plus a full-width Balance (neutral) card, three circular colored
  quick-action buttons in a row (functionally inert — no routes/onClick
  handlers), and a recent-transactions list. Local `useState` for
  `selectedMonth` and `primaryCurrency` (resets to UZS on reload). The
  toggle **fully hides** the non-selected currency in the summary block
  only — switching re-renders instantly from already-fetched
  `by_currency` / `balances` data with no network request; recent
  transactions are never filtered by currency. Income/expense looked up
  by `currency` field with `{ income: 0, expense: 0 }` fallback; balance
  all-time from wallet-balances. Three independent fetch blocks with
  per-block loading/error/retry; summary refetches on month change;
  wallet-balances and recent-transactions fetch once on mount. **i18n**
  (`ru.json`, `uz.json`): home screen strings. **Styles** (`index.css`):
  home layout, metric cards, quick actions, recent-transaction rows.
  Visual polish pass: removed duplicate Home title (shell header suppressed
  on `/`), center-aligned metric card labels/values, shared
  `--app-card-shadow` token with secondary page background so summary cards
  read as elevated white surfaces. `npm run lint` and `npm run build` pass.
