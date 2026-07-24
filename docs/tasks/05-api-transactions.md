# Task 05 — API: Transactions

Depends on: Task 04 (`04-api-wallets-categories.md` — done, verified)
PRD reference: §3, §4.2–§4.4, §6

## Goal

Endpoints for creating Income / Expense / Transfer transactions, plus
generic read/update/delete for a single transaction, with role-based
edit/delete rules (PRD §3) and rate-direction logic for Transfer
(PRD §4.4).

No list/filter endpoint (`GET /transactions` with date range etc.) in
this task — that's History, Task 06.

## Endpoints

| Method | Path | Role | Notes |
|---|---|---|---|
| POST | `/api/v1/transactions/income` | Owner, Member | `transaction_date`, `amount`, `wallet_id`, `income_category_id`, `comment` |
| POST | `/api/v1/transactions/expense` | Owner, Member | `transaction_date`, `amount`, `wallet_id`, `expense_category_id`, `comment` |
| POST | `/api/v1/transactions/transfer` | Owner, Member | `transaction_date`, `wallet_id` (from), `to_wallet_id`, `amount`, `rate` (conditional), `comment` |
| GET | `/api/v1/transactions/{id}` | Owner, Member | Read a single transaction within caller's `family_budget_id` |
| PATCH | `/api/v1/transactions/{id}` | Owner (any), Member (own only) | Same fields as the matching create endpoint; transaction `type` is immutable |
| DELETE | `/api/v1/transactions/{id}` | Owner (any), Member (own only) | Soft-delete |

## Validation common to all types

- `wallet_id` (and `to_wallet_id` for transfer) must belong to the
  caller's `family_budget_id` and have `is_deleted = false` — otherwise
  404.
- `amount` — integer, `> 0`.
- `transaction_date` — required in the request body. The backend does
  not default it to "now"; the frontend is responsible for
  pre-filling it (PRD §4.2–§4.4: datetime picker defaults to now in
  the UI).
- `created_by_user_id` — always taken from the authenticated user
  (Task 01 `initData` auth), never accepted from the request body.

## Income

- `income_category_id` is required, must belong to caller's
  `family_budget_id`, `is_deleted = false` — otherwise 404.

## Expense

- `expense_category_id` is required, must belong to caller's
  `family_budget_id`, `is_deleted = false` — otherwise 404.
- **Confirmed:** the referenced category must be a subcategory
  (`parent_id IS NOT NULL`). Submitting a top-level category id
  (`parent_id IS NULL`) is rejected with 400. This matches the Add
  Expense form (PRD §4.3), which always requires both a category and a
  subcategory selection. All 5 seed top-level categories (Task 03)
  currently have at least one subcategory, so this does not create a
  dead end for MVP. If the Owner later creates a top-level category
  with zero subcategories via Task 04's API, it simply cannot be used
  on a transaction until a subcategory is added — acceptable for MVP,
  not handled specially here.

## Transfer

- `wallet_id` must not equal `to_wallet_id` — otherwise 400.
- If `wallet_id` and `to_wallet_id` have the same currency:
  - `rate` must not be provided (422 if present).
  - `to_amount = amount`.
- If currencies differ (only `UZS`/`USD` exist per PRD §1):
  - `rate` is required, must be `> 0` — otherwise 422.
  - Rate convention (PRD §4.4): `rate` always means "UZS per 1 USD",
    regardless of transfer direction.
    - UZS → USD: `to_amount = round(amount / rate)`
    - USD → UZS: `to_amount = round(amount * rate)`
  - **Confirmed:** `to_amount` is stored as a rounded integer
    (standard rounding, Python `round()`). A sub-unit remainder from
    the division is silently absorbed by rounding — this is an
    accepted simplification for MVP, not flagged to the user.
- `income_category_id` / `expense_category_id` must not be provided
  for a transfer — reject with 422 (`extra="forbid"`, consistent with
  the wallet `PATCH` behavior from Task 04).

## Edit/delete permissions (PRD §3)

- Owner: may `PATCH`/`DELETE` any transaction within their
  `family_budget_id`.
- Member: may `PATCH`/`DELETE` only if `created_by_user_id` equals the
  caller's own user id. Otherwise 403.
- A transaction belonging to a different `family_budget_id` returns
  404, not 403 (consistent with Task 04's cross-family behavior).
- `PATCH` re-runs the same validation as the corresponding create
  endpoint (e.g. changing `amount` or `rate` on a transfer recalculates
  `to_amount`; changing `wallet_id`/`to_wallet_id` re-checks currency
  match and family-budget ownership).

## Acceptance criteria

- [x] All 6 endpoints implemented and role-enforced
- [x] Income/Expense creation validates that `wallet_id` and the
      category belong to the caller's family budget and are not
      soft-deleted
- [x] Expense creation rejects a top-level category id with 400
      (must be a subcategory)
- [x] Transfer: same-currency branch sets `to_amount = amount`, no
      `rate` accepted
- [x] Transfer: different-currency branch requires `rate`, computes
      `to_amount` per the §4.4 formulas with standard rounding
- [x] Transfer rejects `wallet_id == to_wallet_id` with 400
- [x] Transfer rejects `income_category_id`/`expense_category_id` in
      the request body with 422
- [x] Member gets 403 patching/deleting another user's transaction,
      200 on their own
- [x] Owner can `PATCH`/`DELETE` any transaction in their family budget
- [x] Cross-family-budget transaction access returns 404
- [x] `DELETE` performs soft-delete (`is_deleted`, `deleted_at`), no
      cascade

## Verification

Automated verification script, following the pattern of
`backend/scripts/manual_verify_categories.py`:

- Looks up the existing test Owner (`telegram_id=111111`) and Member
  (`telegram_id=222222`) by `telegram_id` — does not create new test
  users. (Test data will be cleaned up separately before the MVP
  release, not as part of this task.)
- Creates any wallets/categories it needs directly via
  `async_session_factory`, with unique names per run (same pattern as
  the Task 04 script), so repeated runs don't collide.
- Exercises each endpoint via `httpx` against the locally running
  server, using `build_init_data` from `scripts/gen_test_initdata.py`
  for both the Owner and Member identities.
- Prints `[PASS]`/`[FAIL]` for every item in "Acceptance criteria"
  above, plus a final summary, exit code 1 on any failure.

## Changelog

- **2026-07-15**: Task 05 implemented. Pydantic schemas in
  `app/schemas/transactions.py` (`IncomeCreate`, `ExpenseCreate`,
  `TransferCreate` with `extra="forbid"`, matching update aliases, and
  `TransactionResponse`). Business logic in `app/services/transactions.py`
  reusing Task 04 wallet/category lookup helpers
  (`get_active_wallet`, `get_active_income_category`,
  `get_active_expense_category`). All 6 endpoints under
  `app/api/v1/transactions.py`, registered in `app/main.py`: POST
  income/expense/transfer (Owner + Member), GET/PATCH/DELETE by id with
  family-budget scoping (404 cross-family), expense subcategory
  requirement (400 for top-level `parent_id IS NULL`), transfer
  same-currency vs cross-currency branches with PRD §4.4 rate formulas
  and Python `round()`, edit/delete permission rules (Owner any, Member
  own only → 403). No new migration — Task 02 `transactions` schema was
  sufficient. Unit tests in `backend/tests/test_transactions.py`:
  12/12 pass; full backend suite 40/40 pass.
- **2026-07-15 (deviation — intentional, not a spec conflict)**: API
  routes use `/api/v1/…` prefix to match Task 01/04 convention; the
  task endpoint table lists paths without the prefix. `PATCH
  /transactions/{id}` reads the raw JSON body and validates against the
  schema matching the existing transaction's immutable `type` (income,
  expense, or transfer) rather than exposing three separate PATCH
  routes — same fields and validation as the corresponding create
  endpoint, as specified.
- **2026-07-15 (manual verification script)**: added
  `backend/scripts/manual_verify_transactions.py` — exercises every
  Acceptance criteria item via `httpx` against a running local server,
  using test Owner (`telegram_id=111111`) and Member
  (`telegram_id=222222`); creates wallets/categories directly via
  `async_session_factory` with unique names per run. Run manually after
  starting the server: `python -m scripts.manual_verify_transactions`.
