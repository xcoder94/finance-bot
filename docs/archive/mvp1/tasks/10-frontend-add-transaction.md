# Task 10 — Frontend: Add Income / Add Expense / Add Transfer forms

Depends on: Task 09 (`09-frontend-home.md` — done), Task 05
(`05-api-transactions.md` — done, backend confirmed sufficient, no
changes needed), Task 04 (`04-api-wallets-categories.md` — done)
PRD reference: §4.2 (Add Income), §4.3 (Add Expense), §4.4 (Add Transfer)

## Goal

Replace the disabled quick-action buttons on Home (Task 09) with three
working forms: Add Income, Add Expense, Add Transfer. Each form is a new
top-level route, outside the existing `AppLayout` (no Tabbar). On
successful submit, show a confirmation modal with two options; on
failure, show an inline error with Retry. Returning to Home must show
fresh data.

## Reference mockups

Four screenshots are provided alongside this task file (attach as
Cursor context): "Добавление дохода", "Добавление расхода", "Перевод /
обмен валюты" (same-currency wallets — no rate field), "Перевод / обмен
валюты" (different-currency wallets — rate field + live-calculator
result visible). These are the source of truth for visual structure:
**layout, spacing, card style, colors, field order, button style must
match these screenshots as closely as practical with TelegramUI
components** — this is not just a functional spec, matching the visual
design precisely is part of the acceptance criteria for this task, the
same way it was for Task 09. Where a mockup and this document conflict
on data/behavior (not visual style), this document wins — ask before
guessing.

## Routing

Three new top-level routes, **outside** `AppLayout` (defined in
`AppShell.tsx` alongside the existing `<Routes>`, not nested under the
`AppLayout` route): `/add-income`, `/add-expense`, `/add-transfer`. No
Tabbar on these pages. Each page has its own lightweight header: "‹ Мои
финансы" button (navigates to `/`) on the left, form title on the
right/center — per mockups.

Home's three quick-action buttons (Task 09, currently inert) become
real navigation:
- Green "+" → `/add-income`
- Red "−" → `/add-expense`
- Gray "⇄" → `/add-transfer`

## Shared behavior across all three forms

### Fields common to all forms
- **Дата и время** — **not** a native `datetime-local` input (reverted
  after verification — see "Why not native datetime-local" below).
  Custom masked text input, format `ДД.ММ.ГГГГ, ЧЧ:ММ`:
  - Controlled input, digits-only entry: any non-digit keypress is
    ignored outright (nothing inserted, no error shown — the keypress
    simply has no effect). This is deliberate: it protects against
    stray/misclicks without needing a picker UI.
  - Separators (`.`, `.`, `,`, `:`) are inserted automatically as the
    user types digits — the user never types them directly.
  - Backspace removes the last typed digit and reformats.
  - Defaults to the current date/time on form load, pre-filled in this
    same format.
  - On blur or submit, validate it's a real calendar date/time (correct
    days-per-month including leap years, hour 0–23, minute 0–59) —
    inline error if not, same pattern as other field validation.
  - Convert to an ISO datetime string before sending in the POST body
    — same wire format as before, this only changes the input UI.
  - No date-picker library — plain controlled input + manual
    parsing/formatting, consistent with the rest of the form code.

  **Why not native `datetime-local`**: its displayed format is
  controlled by the user's OS locale, not by the page — there is no
  HTML/CSS/JS way to force `DD.MM.YYYY` display across browsers/OSes.
  The mockup's `07/19/2026, 04:52 PM` was simply this developer
  machine's OS locale rendering, not a deliberate format choice — do
  not treat that screenshot format as a spec for this field.
- **Сумма** (and **Курс** on Add Transfer) — starts **empty**, not
  pre-filled with `0`; `0` is shown only as a greyed `placeholder`.
  Digits-only entry, **live space-separated thousands formatting as
  the user types** — e.g. typing `1234567` displays as `1 234 567` in
  the field in real time (reuse the same space-separator convention as
  `formatCurrency.ts`, but this is a live-editing display, not the
  final formatted currency string with `$`/`UZS`). The underlying
  value used for validation/submission is always the raw digit string
  with spaces stripped — spaces are a display-only aid, never part of
  the actual number. Hard cap at **10 raw digits** (spaces don't count
  toward this limit) — an attempted 11th digit is rejected outright
  (not inserted), and the field gets an error/invalid visual state (red
  border) for as long as its content is invalid (i.e., while at the
  10-digit cap after a rejected keystroke is a normal, non-error state
  — only actually-invalid content, if any is later allowed, should be
  red; for this task the only trigger is the moment of a rejected
  11th-digit keystroke, clearing on the next valid edit). Reason: the
  backend `amount`/`rate` columns are effectively bounded by Postgres
  `INTEGER` (32-bit, ~2.1 billion / 10 digits) — values above that
  previously reached the database and caused a 500 error instead of a
  clean validation message; blocking at 10 digits on the frontend
  prevents that case entirely.
- **Комментарий (необязательно)** — multiline text input, optional,
  always the last field before the buttons.
- **Отменить** / **Добавить** buttons at the bottom — "Отменить"
  navigates to `/`, "Добавить" submits the form.

### Validation
Local `useState` + manual checks on submit. No new dependencies
(react-hook-form/zod not used — consistent with the rest of the app).
Required fields per form type (see below) must be filled; amount must
be a positive number. Show inline validation errors near the relevant
field on failed submit attempt — do not block typing.

### Submission error handling
If the POST request fails (network error, 4xx/5xx): inline error
message on the form + a "Повторить" (Retry) button, same visual pattern
as the existing `BlockError` component from Home (Task 09). No
`toast`, no `alert()`.

### Success behavior
On successful `201` response:
1. Show a modal with two options: **"На главную"** (navigate to `/`)
   and **"Добавить ещё"** (close the modal only).
2. Clear all form fields immediately on success (before or as the modal
   appears) — regardless of which modal option the user later picks.
3. "Добавить ещё" keeps the user on the same form type, now empty —
   never switches to a different form type or navigates to Home first.

### Return-to-Home refetch
No special code needed — navigating to `/` unmounts/remounts `HomePage`
as a normal React Router route, which re-triggers all three
`useFetchBlock` calls (Task 09). **Must be confirmed manually in the
browser during verification** — do not treat as proven by code alone.

## Add Income (`/add-income`)

Fields, top to bottom (per mockup 1): Дата и время, Сумма, Кошелёк,
Категория, Комментарий.

- **Сумма** — positive integer, no currency symbol shown in the field
  itself (currency is implied by the selected wallet).
- **Кошелёк** — select, populated from `GET /api/v1/wallets`. Label
  format: `"{name} ({currency})"` e.g. "Основной (UZS)" — matches
  mockup. Wallet list is guaranteed non-empty (min. 4 seeded wallets).
- **Категория** — select, populated from `GET
  /api/v1/categories/income`. Flat list, no hierarchy.

Submit → `POST /api/v1/transactions/income` with `transaction_date,
amount, wallet_id, income_category_id, comment?`.

## Add Expense (`/add-expense`)

Fields, top to bottom (per mockup 2): Дата и время, Сумма, Кошелёк,
Категория, Подкатегория, Комментарий.

- **Сумма**, **Кошелёк** — same as Add Income.
- **Категория** — select, populated from `GET
  /api/v1/categories/expense`, filtered to `parent_id == null`
  (top-level only).
- **Подкатегория** — select, populated by filtering the same
  `GET /api/v1/categories/expense` response a second time, this time to
  `parent_id == selected top-level category's id`. Recomputed every
  time "Категория" changes.
  - If subcategories exist for the selected category: default-select
    the first one, user can change it.
  - If none exist: **do not show an empty/disabled subcategory field**.
    Instead, right before submitting the transaction, the frontend
    itself calls `POST /api/v1/categories/expense` with `{ name:
    "Общее", parent_id: <selected top-level category id> }`, takes the
    returned id, and uses it as `expense_category_id`. This is a
    deliberate temporary measure (see PRD/roadmap note on Task 13) —
    do not build any additional UI around it (no "name your
    subcategory" input, no confirmation step).

Submit → `POST /api/v1/transactions/expense` with `transaction_date,
amount, wallet_id, expense_category_id (leaf/subcategory id, never the
top-level id), comment?`.

## Add Transfer (`/add-transfer`)

Fields, top to bottom (per mockups 3 & 4): Дата и время,
Кошелёк-источник, Кошелёк-получатель, Сумма, [Курс — conditional],
[live-calculator result — conditional], Комментарий.

- **Кошелёк-источник** / **Кошелёк-получатель** — two selects, same
  `GET /api/v1/wallets` list, same `"{name} ({currency})"` label
  format. Selecting the same wallet in both must be prevented or
  rejected on submit with a clear inline message (backend also rejects
  this — `wallet_id must not equal to_wallet_id`).
- **Сумма** — label dynamically includes the source wallet's currency
  in parentheses, e.g. `"Сумма (UZS)"` or `"Сумма (USD)"` (mockup 3 vs
  4) — always the currency of Кошелёк-источник, updates if the user
  changes that selection.
- **Курс** — conditional field:
  - **Hidden entirely** (not disabled, not rendered) when source and
    destination wallets have the same currency (mockup 3).
  - **Shown and required** when currencies differ (mockup 4). Label:
    exactly **"Курс (UZS за 1 USD)"** regardless of transfer direction
    — the rate always means "how many UZS per 1 USD".
- **Live-calculator result line** — conditional, shown only alongside
  the Курс field (i.e. only for cross-currency transfers). Read-only,
  not an input. Per mockup 4: label "Получит кошелёк" on the left,
  computed amount in the destination currency on the right, **green
  text**, e.g. `"0 UZS"`. Recomputes instantly on every change to
  Сумма or Курс (both editable) — no debounce needed, no network call.
  - UZS → USD: `to_amount = amount / rate`
  - USD → UZS: `to_amount = amount × rate`
- When currencies match: `to_amount = amount`, `rate` is not sent to
  the backend (or sent as `null`).

Submit → `POST /api/v1/transactions/transfer` with `transaction_date,
wallet_id, to_wallet_id, amount, rate? (omit/null if same currency),
comment?`. Do not send a frontend-computed `to_amount` — the backend
computes and stores it itself (see `compute_transfer_amounts` in
`app/services/transactions.py`); sending it would violate the
`extra="forbid"` schema config and be rejected with 422.

## Number formatting

Reuse `frontend/src/utils/formatCurrency.ts` as-is for the
live-calculator result display. Do not reformat the raw amount input
fields as the user types (keep them plain numeric inputs) — formatting
is only for the read-only result line.

## i18n

Add new keys to `ru.json` / `uz.json` for: form titles, field labels
("Дата и время", "Сумма", "Кошелёк", "Категория", "Подкатегория",
"Кошелёк-источник", "Кошелёк-получатель", "Курс (UZS за 1 USD)",
"Получит кошелёк", "Комментарий (необязательно)"), buttons ("Отменить",
"Добавить", "Повторить"), success modal ("На главную", "Добавить
ещё"), and any validation-error strings. Follow the existing key-naming
convention from `home.*` (Task 09) — e.g. `addIncome.*`,
`addExpense.*`, `addTransfer.*`.

## Out of scope for this task

- Editing or deleting existing transactions (no UI anywhere yet).
- Any change to backend endpoints, schemas, or services — Task 05
  already covers everything these forms need.
- Persisting draft form state across navigation.
- Improving the auto-created "Общее" subcategory flow beyond what's
  described above (explicitly deferred to Task 13).
- A currency filter, unit toggle, or anything not shown in the 4
  mockups.

## Acceptance criteria

- [x] Home's three quick-action buttons navigate to `/add-income`,
      `/add-expense`, `/add-transfer` respectively; no console errors.
- [x] Each form's header shows "‹ Мои финансы" and returns to `/` on
      click; no Tabbar visible on any of the three routes.
- [x] Add Income: submits successfully with valid data; wallet and
      category selects populated from real API data; validation blocks
      submit with missing/invalid fields and shows inline errors.
- [x] Add Expense: Категория/Подкатегория two-step select works;
      subcategory list re-filters correctly when category changes;
      when a category has no subcategories, a "Общее" subcategory is
      auto-created via API and used, with no extra UI shown for this.
- [x] Add Transfer: Курс field and live-calculator result are hidden
      for same-currency wallet pairs, shown and required for
      cross-currency pairs; live-calculator recomputes instantly on
      Сумма/Курс change with no network request; correct direction
      formula applied (UZS→USD divides, USD→UZS multiplies); selecting
      the same wallet for source and destination is prevented or
      cleanly rejected.
- [x] On successful submit (any form): confirmation modal appears with
      "На главную" and "Добавить ещё"; fields are cleared immediately;
      "На главную" navigates to `/`, "Добавить ещё" closes the modal
      and keeps the same empty form.
- [x] On failed submit (any form): inline error + "Повторить" button
      appears on the form itself, not a toast/alert; retry re-submits
      with the current field values.
- [x] Returning to `/` after adding a transaction shows updated Home
      data (summary, balances, recent transactions) — confirmed by
      actually adding a transaction and observing Home refresh, not
      just by code inspection.
- [x] Visual layout, spacing, colors, and field order match the 4
      reference mockups as closely as practical with TelegramUI
      components.
- [x] Дата и время field is a masked text input (`ДД.ММ.ГГГГ, ЧЧ:ММ`),
      not a native `datetime-local` input; non-digit keystrokes have no
      effect; separators auto-insert; invalid calendar dates are
      rejected inline on blur/submit; defaults to current date/time.
- [x] Сумма field (all three forms) and Курс field (Add Transfer) start
      empty with `0` as placeholder only, never a real pre-filled `0`;
      as digits are typed, the field displays them with space-separated
      thousands live (e.g. `1 234 567`) while the underlying value
      stays the raw unspaced digit string.
- [x] Сумма/Курс fields accept up to 10 digits (spaces excluded from
      the count); an 11th digit is rejected and the field shows a
      red/invalid state until corrected.
- [x] No TypeScript / build errors; `npm run dev` runs clean.

## Verification

Manual, in browser, step by step:

1. From Home, click each quick-action button — confirm correct
   navigation, correct header, no Tabbar, no console errors.
2. Add Income: fill and submit a valid income — confirm 201 in Network
   tab, confirm success modal appears, confirm form fields are cleared.
3. Click "Добавить ещё" — confirm modal closes, form stays on
   `/add-income`, fields are empty. Submit a second income.
4. Click "На главную" after a third submit — confirm navigation to `/`
   and confirm the new transactions appear in Home's summary/recent
   list without a manual reload.
5. Add Expense: select a category with existing subcategories —
   confirm subcategory list updates; select a category with none —
   submit, then check (via a follow-up expense list or DB, as
   available) that a "Общее" subcategory was created under the right
   parent.
6. Add Transfer, same-currency wallets — confirm Курс field and result
   line are entirely absent; submit successfully.
7. Add Transfer, cross-currency wallets — confirm Курс field and
   live-calculator result appear; change Сумма and Курс independently,
   confirm the result updates instantly and correctly for both
   UZS→USD and USD→UZS directions; submit successfully.
8. Try submitting each form with missing required fields — confirm
   inline validation errors, no request sent.
9. Stop the backend, attempt a submit on each form — confirm inline
   error + Retry appears; restart backend, click Retry — confirm it
   succeeds.
10. Compare each form side-by-side against its reference mockup —
    confirm layout/spacing/colors match closely.
11. Дата и время field: try typing letters/symbols — confirm nothing
    is inserted; type a full valid date/time — confirm it displays and
    submits correctly; type an invalid calendar date (e.g. 31.02.2026)
    — confirm inline validation error, no request sent.
12. Сумма field (each form): confirm it's empty with greyed `0`
    placeholder on load, not a real `0`. Type `1234567` — confirm it
    displays live as `1 234 567` while typing (not just after blur).
    Type 10 digits — confirm all accepted; type an 11th — confirm
    rejected and field turns red; delete a digit — confirm red state
    clears. Confirm the submitted amount matches the raw digits with
    no spaces. Repeat for Курс field on Add Transfer.

## Changelog

- **2026-07-20**: Task 10 implemented. **Routing** (`AppShell.tsx`): added
  `/add-income`, `/add-expense`, `/add-transfer` as top-level routes outside
  `AppLayout` (no Tabbar), each with a `‹ Мои финансы` back link and form
  title. **Home** (`HomePage.tsx`): wired quick-action buttons to the three
  routes. **API layer** (`frontend/src/api/transactions.ts`): typed fetch
  helpers for wallets, income/expense categories, expense-category create,
  and income/expense/transfer create endpoints via `getAuthHeader()`.
  **Shared form UI** (`frontend/src/components/transaction-form/
  TransactionFormShared.tsx`): layout shell, Cancel/Add footer, load/submit
  error blocks (Home `BlockError` pattern), success modal ("На главную" /
  "Добавить ещё"), `MaskedDateTimeInput` and `LimitedDigitInput` field
  components. **Utils** (`frontend/src/utils/transactionForm.ts`): masked
  datetime formatting/parsing/validation (`ДД.ММ.ГГГГ, ЧЧ:ММ` → ISO),
  wallet labels, positive-integer parsing, transfer `to_amount` calculation
  matching backend `compute_transfer_amounts`, 10-digit cap constant,
  space-separated thousands formatting helpers and cursor-position utilities
  for live-editing numeric fields. **Pages**: `AddIncomePage.tsx`,
  `AddExpensePage.tsx` (two-step category/subcategory with auto-created
  `"Общее"` fallback), `AddTransferPage.tsx` (conditional rate + live
  calculator for cross-currency, same-wallet prevention, no `to_amount` in
  POST body). **Input behavior** (verification-driven, no backend changes):
  replaced native `datetime-local` with masked text input (digits-only,
  auto-inserted separators, inline error on invalid calendar date);
  amount/rate fields start empty with `placeholder="0"`, reject an 11th
  digit with red border, and format digits with live space-separated
  thousands as the user types while parent state and POST payloads keep
  the raw unspaced digit string. **i18n** (`ru.json`, `uz.json`): form
  titles, field labels, buttons, success modal, `addTransaction.invalidDateTime`.
  **Styles** (`index.css`): transaction form layout, action buttons,
  receive-row calculator, field-error text. `npm run lint` and `npm run build`
  pass.
