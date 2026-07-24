# Task 06 — API: History & Analytics

Depends on: Task 05 (`05-api-transactions.md` — done, verified)
PRD reference: §4.5, §4.6

## Goal

Read-only query endpoints for transaction History (paginated date-range
list) and Analytics (category breakdowns, trend, summary). Both Owner and
Member have full read access. No schema changes — all data comes from the
Task 02 `transactions` table and related entities.

## Endpoints

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/api/v1/transactions/history` | Owner, Member | `date_from`, `date_to` required (ISO 8601 datetimes); `limit`/`offset` pagination |
| GET | `/api/v1/analytics/expenses-by-category` | Owner, Member | Top-level expense categories only; subcategory amounts rolled up |
| GET | `/api/v1/analytics/expenses-by-subcategory` | Owner, Member | `parent_category_id` required; drill-down for one top-level category |
| GET | `/api/v1/analytics/income-by-category` | Owner, Member | Income grouped by category |
| GET | `/api/v1/analytics/trend` | Owner, Member | Last 12 calendar months; no query params |
| GET | `/api/v1/analytics/summary` | Owner, Member | Per-currency totals, transfer net, day-of-week breakdown |

## History

- `date_from` / `date_to` — **required** ISO 8601 datetimes (not date-only).
  422 if either is missing or if `date_from > date_to`.
- `limit` (default 50, max 500) and `offset` (default 0) for pagination.
- Returns `{ items, total_count }` sorted by `transaction_date DESC`.
- Excludes soft-deleted transactions (`is_deleted = false`).
- Each item includes wallet/category names joined from related tables
  (including soft-deleted categories/wallets — historical display).
- `created_by` (author display name) is included on **every** item or
  omitted from **every** item based on a single
  `COUNT(users WHERE family_budget_id = …)` including soft-deleted users.
  If count ≥ 2 → include; if count == 1 → omit the field entirely.
  Never a per-row conditional.

## Analytics date ranges

- All analytics endpoints except `trend` accept optional `date_from` /
  `date_to` (ISO 8601 datetimes). When both omitted, default to the
  **current calendar year** (Jan 1 00:00 UTC – Dec 31 23:59:59.999999 UTC).
  When one is provided without the other → 422.
- `trend` accepts **no** query parameters. Always returns the last 12
  calendar months ending with the current month, regardless of any params
  passed.

## Expenses by category / subcategory

- `expenses-by-category` — aggregates expense amounts to **top-level**
  categories only (`parent_id IS NULL` on the rolled-up parent). Each
  expense transaction references a subcategory; its amount is summed into
  the subcategory's parent.
- `expenses-by-subcategory` — requires `parent_category_id`. Validates
  that the id is a non-deleted top-level expense category belonging to
  the caller's family budget; otherwise 404. Returns amounts grouped by
  direct subcategories of that parent.

## Currency scoping for category endpoints (fix, 2026-07-18)

**Bug found during frontend design audit:** `expenses-by-category`,
`expenses-by-subcategory`, and `income-by-category` currently sum
`amount` across all wallet currencies for a given category, without
regard to currency. Since UZS and USD amounts must never be merged
(PRD §6), a category with transactions in both currencies returns a
meaningless combined number.

**Fix:** add a required `currency` query parameter (`UZS` or `USD`) to
all three endpoints. Each call is scoped to one currency; the response
only includes categories that have transaction activity in that
currency. 422 if `currency` is missing or not one of `UZS`/`USD`.
This matches the existing per-currency pattern already used by
`summary` and (implicitly, via wallet currency) transaction storage —
no schema change required.

## Summary formulas

Per currency in the selected date range:

- `income` — sum of income transaction amounts (wallet currency).
- `expense` — sum of expense transaction amounts (wallet currency).
- `transfer_net` — for each transfer: subtract `amount` from the
  from-wallet's currency, add `to_amount` to the to-wallet's currency.
- `net_change` — `income - expense + transfer_net`.
- `average_daily_expense` — `expense // elapsed_days`, where
  `elapsed_days = (min(date_to, today) - date_from).days + 1` (minimum 1).
- `day_of_week_expense` / `day_of_week_income` — 7-element arrays indexed
  by Python weekday (0 = Monday … 6 = Sunday), per currency.

## Acceptance criteria

- [x] `GET /transactions/history` returns paginated items + total_count,
      sorted `transaction_date DESC`, excluding soft-deleted transactions
- [x] History requires `date_from`/`date_to` as ISO 8601 datetimes; 422
      when missing or when `date_from > date_to`
- [x] `created_by` included on all items or omitted from all items based
      on family user count (including soft-deleted users), never per-row
- [x] `expenses-by-category` returns top-level categories with subcategory
      amounts rolled up
- [x] `expenses-by-subcategory` requires valid top-level `parent_category_id`;
      404 for subcategory id or cross-family parent
- [x] Analytics endpoints (except trend) default to current calendar year
      when date range omitted
- [x] `trend` always returns last 12 months; ignores any query params
- [x] `summary` computes `transfer_net` with correct sign in both transfer
      directions (UZS→USD and USD→UZS)
- [x] `average_daily_expense` uses elapsed days for in-progress periods
- [x] `day_of_week_expense` and `day_of_week_income` aggregate correctly
- [x] Member has full read access to all 6 endpoints (no 403s)
- [x] Owner and Member both allowed; no `require_owner` on any endpoint
- [x] `expenses-by-category`, `expenses-by-subcategory`,
      `income-by-category` require `currency` (UZS/USD) and only sum
      transactions in that currency; 422 if missing/invalid

## Verification

Automated verification script, following the pattern of
`backend/scripts/manual_verify_transactions.py`:

- Looks up the existing test Owner (`telegram_id=111111`) and Member
  (`telegram_id=222222`) by `telegram_id` — does not create new test users.
- Creates wallets/categories/transactions directly via
  `async_session_factory`, with unique names per run, known amounts, and
  dates spread across at least 2 months and 2 weekdays.
- Exercises all 6 endpoints via `httpx` against the locally running server,
  using `build_init_data` from `scripts/gen_test_initdata.py` for both
  identities.
- Prints `[PASS]`/`[FAIL]` for every item in "Acceptance criteria" above,
  plus a final summary, exit code 1 on any failure.

## Changelog

- **2026-07-17**: Task 06 implemented. Pydantic response schemas in
  `app/schemas/history_analytics.py` (`HistoryItem`, `HistoryResponse`,
  `CategoryAmount`, `SubcategoryAmount`, `TrendEntry`, `PerCurrencySummary`,
  `SummaryResponse`; all with `extra="forbid"`). Business logic in
  `app/services/history_analytics.py`: paginated history with joined
  wallet/category names, family-wide `created_by` visibility toggle,
  top-level expense rollup + subcategory drill-down, income-by-category,
  fixed 12-month trend, per-currency summary with transfer_net direction
  logic, elapsed-days average daily expense, and day-of-week arrays.
  Routes in `app/api/v1/history.py` and `app/api/v1/analytics.py`,
  registered in `app/main.py` (history router before transactions router
  so `/transactions/history` is not captured by `/{transaction_id}`).
  No new migration — Task 02 schema was sufficient. Unit tests in
  `backend/tests/test_history_analytics.py`: 15/15 pass; full backend
  suite 55/55 pass.
- **2026-07-17 (manual verification script)**: added
  `backend/scripts/manual_verify_history_analytics.py` — exercises every
  Acceptance criteria item via `httpx` against a running local server,
  using test Owner (`telegram_id=111111`) and Member
  (`telegram_id=222222`); creates wallets/categories/transactions directly
  via `async_session_factory` with unique names per run. Run manually after
  starting the server: `python -m scripts.manual_verify_history_analytics`.
- **2026-07-17 (verification script corrected)**: the manual
  verification script (`backend/scripts/manual_verify_history_analytics.py`)
  was rewritten to compare deltas against a pre-insertion baseline
  instead of absolute totals, since test data accumulates across runs
  by project convention. The original agent-written version produced
  false [FAIL]s caused by leftover data from prior runs, not actual API
  bugs. All 36 checks pass against the corrected script.
- **2026-07-17 (clarification)**: `average_daily_expense` uses integer
  floor division (`expense // elapsed_days`), not rounding. Not
  explicitly specified in the task file; confirmed correct behavior,
  documenting here for traceability.
- **2026-07-18 (currency-scoping fix)**: `expenses-by-category`,
  `expenses-by-subcategory`, `income-by-category` now require a
  `currency` query parameter (UZS/USD); previously these endpoints
  summed transactions across currencies for the same category, which
  produced meaningless combined totals. Fixed in
  `app/services/history_analytics.py` and `app/api/v1/analytics.py`;
  unit tests updated in `backend/tests/test_history_analytics.py`
  (18/18 pass; full suite 58/58). Verified manually with
  `backend/scripts/manual_verify_currency_scoping.py` (14/14 PASS) —
  confirmed a single category with transactions in both UZS and USD
  now returns correctly separated amounts (previously merged).