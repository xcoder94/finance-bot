# Task 04 — API: Wallets & Categories

Depends on: Task 03 (`03-bot-onboarding.md` — done, verified)
PRD reference: §3, §4.7, §5, §7

## Goal

CRUD endpoints for `wallets`, `income_categories`, `expense_categories`.
Owner-only for create/rename/delete. Members can only read (GET) for
use in transaction forms (Task 05/09).

## Step 0 — Schema addition (follow-up migration)

`wallets.currency` was created as a free-text `string` in Task 02.
Add a new Alembic migration (do not edit the original migration,
already applied) that:

- Adds a CHECK constraint restricting `wallets.currency` to
  `'UZS'` or `'USD'` only.
- Existing rows (if any test data present) must already satisfy this —
  confirm before applying.

At the application layer, `currency` is also validated as an enum
(`"UZS" | "USD"`) in the Pydantic request schema for `POST /wallets` —
belt-and-suspenders with the DB constraint, since the DB constraint
alone would only reject at insert time with a raw Postgres error, not
a clean 422 API response.

Rationale: prevents duplicate/inconsistent currency values (e.g.
`"usd"`, `"Usd"`, typos) that would silently break per-currency
summaries (PRD §6). Only two currencies supported at MVP launch, per
PRD §1/§6 — not a general multi-currency system.

## Delete behavior (resolves PRD §7 open question)

`DELETE` performs soft-delete immediately — no blocking confirmation
step in the API (`is_deleted = true`, `deleted_at = now()`). No cascade
to `transactions`.

To support a future frontend confirmation UX (decided at Task 12, not
now), the API exposes transaction counts:

- `GET /wallets`, `GET /categories/income`, `GET /categories/expense` —
  each item includes `transaction_count` (number of non-deleted
  transactions referencing this record).
- `DELETE /wallets/{id}`, `DELETE /categories/{id}` — response includes
  `affected_transactions_count` (same meaning, at time of deletion).

No `force` flag, no 409 status, no two-step confirm in this task. If
Task 12 decides a hard-block confirm is needed, it can be added later
via a `force` query param without changing schema or existing behavior.

## Endpoints

### Wallets

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/wallets` | Owner, Member | Returns non-deleted wallets for caller's `family_budget_id`, with `transaction_count` |
| POST | `/wallets` | Owner | Body: `name`, `currency` (enum: `UZS`\|`USD`, see Step 0) |
| PATCH | `/wallets/{id}` | Owner | Rename only (`name`). Currency not editable after creation — changing currency on a wallet with existing transactions would silently corrupt per-currency summaries (PRD §6); if currency needs to change, delete and recreate |
| DELETE | `/wallets/{id}` | Owner | Soft-delete, see above |

### Income categories

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/categories/income` | Owner, Member | Non-deleted, with `transaction_count` |
| POST | `/categories/income` | Owner | Body: `name`. Single-level, no `parent_id` (PRD §5) |
| PATCH | `/categories/income/{id}` | Owner | Rename only |
| DELETE | `/categories/income/{id}` | Owner | Soft-delete |

### Expense categories

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/categories/expense` | Owner, Member | Non-deleted, with `transaction_count`, returned as flat list with `parent_id` — frontend groups into tree (Task 12), not the API's job |
| POST | `/categories/expense` | Owner | Body: `name`, `parent_id` (nullable). If `parent_id` given, must reference an existing non-deleted top-level category (`parent_id IS NULL` on the target) — reject 2-level-deep nesting with 400 |
| PATCH | `/categories/expense/{id}` | Owner | Rename only. Moving between parent/top-level not supported in this task (not in PRD scope for MVP) |
| DELETE | `/categories/expense/{id}` | Owner | Soft-delete. If target is a top-level category with non-deleted subcategories, **also soft-deletes all its subcategories** in the same transaction (see below) |

**Top-level category delete cascade (confirmed — deferred re-evaluation
to v2):** soft-deleting a parent category also soft-deletes its
(non-deleted) subcategories, in the same DB transaction — otherwise
subcategories would remain selectable under a hidden parent, breaking
the Add Expense form (PRD §4.3, category → subcategory is dependent).
This is a soft-delete cascade only (marking `is_deleted`), not a hard
cascade — historical transactions are untouched either way, consistent
with §7. Whether this should instead block deletion (400, "delete
subcategories first") is left as a v2 open question, not revisited in
MVP.

## Permission enforcement

All POST/PATCH/DELETE endpoints: 403 if caller's `role != "owner"`.
Reuses the auth dependency from Task 01 (`initData` validation) plus a
role check against the `users` row resolved from `telegram_id`.

All endpoints scope by caller's `family_budget_id` — a wallet/category
belonging to a different family budget returns 404, not 403 (avoid
leaking existence of other families' data).

## Acceptance criteria

- [ ] Migration adds CHECK constraint on `wallets.currency` (`UZS`/`USD` only), reversible
- [ ] All 12 endpoints implemented and role-enforced
- [ ] `GET` endpoints exclude `is_deleted = true` rows, include `transaction_count`
- [ ] `DELETE` sets `is_deleted`/`deleted_at`, returns `affected_transactions_count`, no cascade to `transactions`
- [ ] Expense category delete cascades soft-delete to its subcategories
- [ ] Expense category create rejects `parent_id` pointing to a subcategory (400)
- [ ] `POST /wallets` rejects a `currency` value outside `UZS`/`USD` with 422
- [ ] Member role gets 403 on all POST/PATCH/DELETE
- [ ] Cross-family-budget access returns 404
- [ ] Wallet `currency` immutable after creation (PATCH ignores/rejects it)

## Verification

1. Apply the new migration, confirm the CHECK constraint exists via
   `psql` (`\d+ wallets`), confirm `alembic downgrade -1` removes it
   cleanly.
2. As Owner: create a wallet with `currency=UZS`, rename it, confirm
   it appears correctly in `GET /wallets`.
3. As Owner: attempt to create a wallet with `currency=EUR` → confirm
   422 response, no row created.
4. As Owner: create expense category "Тест" (top-level), then a
   subcategory under it, confirm both appear with correct `parent_id`.
5. As Member: attempt POST/PATCH/DELETE on wallet and category →
   confirm 403 on all.
6. Manually insert a test transaction via `psql` referencing an
   existing category (exact steps shown when we reach this task), then
   `DELETE` that category via the API → confirm
   `affected_transactions_count = 1`, category disappears from `GET`,
   transaction row untouched in `psql`.
7. Delete a top-level expense category with 2 subcategories → confirm
   all 3 rows get `is_deleted = true` in `psql`.
8. Attempt `POST /categories/expense` with `parent_id` pointing at an
   existing subcategory (not top-level) → confirm 400.
9. Attempt to access a wallet belonging to a different
   `family_budget_id` → confirm 404.

## Changelog

- **2026-07-15**: Task 04 implemented. Added reversible migration
  `d4e5f6a7b8c9` (`ck_wallets_currency` CHECK on `wallets.currency`
  restricting to `UZS`/Task 05 is implemented. Summary:

What was built
Schemas — backend/app/schemas/transactions.py
Request/response models with exact field names from the spec. TransferCreate uses extra="forbid" to reject category fields with 422.

Service — backend/app/services/transactions.py
Validation and business logic reusing Task 04 helpers (get_active_wallet, get_active_income_category, get_active_expense_category):

Wallet/category ownership + is_deleted → 404
Expense top-level category → 400
Transfer same-currency / cross-currency branches with PRD §4.4 formulas and round()
Owner/Member edit/delete permission checks
API — backend/app/api/v1/transactions.py (registered in main.py)

Method	Path	Access
POST
/api/v1/transactions/income
Owner, Member
POST
/api/v1/transactions/expense
Owner, Member
POST
/api/v1/transactions/transfer
Owner, Member
GET
/api/v1/transactions/{id}
Owner, Member
PATCH
/api/v1/transactions/{id}
Owner (any), Member (own)
DELETE
/api/v1/transactions/{id}
Owner (any), Member (own) — soft-delete
Tests — backend/tests/test_transactions.py: 12/12 pass
Full suite: 40/40 pass
No migration needed — Task 02 schema was sufficient.

Manual verification — backend/scripts/manual_verify_transactions.py
Run with the server up:

cd backend && source venv/bin/activate
python -m scripts.manual_verify_transactions
Intentional deviation
PATCH /transactions/{id} reads the raw body and validates against the schema for the existing transaction’s immutable type (one route, three schemas) instead of three separate PATCH endpoints. Same fields and validation as the corresponding create endpoint.

Changelog and acceptance criteria in docs/tasks/05-api-transactions.md are updated.`USD`). Pydantic schemas in
  `app/schemas/wallets_categories.py`. Auth deps in `app/auth/user_deps.py`
  (`get_current_user`, `require_owner`) layered on Task 01 initData
  validation. All 12 endpoints under `app/api/v1/wallets.py` and
  `app/api/v1/categories.py`, registered in `app/main.py`: wallet and
  category CRUD with owner-only writes, family-budget scoping (404 for
  cross-family), `transaction_count` on GET, `affected_transactions_count`
  on DELETE, expense parent_id validation (400 for nesting under a
  subcategory), top-level expense delete soft-delete cascade to
  subcategories in one transaction. `get_session` DB dependency added to
  `app/db.py`. Unit tests in `backend/tests/test_wallets_categories.py`:
  11/11 pass; full backend suite 28/28 pass.
- **2026-07-15 (deviation — intentional, not a spec conflict)**: API
  routes use `/api/v1/…` prefix to match the existing Task 01 `/api/v1/me`
  convention; the task endpoint table lists paths without the prefix.
  Wallet PATCH rejects unknown fields (`currency` included) via Pydantic
  `extra="forbid"` rather than silently ignoring — satisfies the spec's
  "ignores/rejects" requirement with the stricter option.
- **2026-07-15 (manual verification — 13 checks passed)**: full manual
  verification against the Verification checklist, performed via
  curl and a purpose-built async script
  (`backend/scripts/manual_verify_categories.py`) against a running
  local server, using test Owner (`telegram_id=111111`) and Member
  (`telegram_id=222222`) accounts inserted directly via `psql`.
  1. Migration `d4e5f6a7b8c9` applied cleanly; `ck_wallets_currency`
     CHECK constraint confirmed present via `psql \d+ wallets`;
     `alembic downgrade -1` removed it cleanly, `alembic upgrade head`
     restored it.
  2. Owner wallet CRUD: created, renamed, listed — all correct.
  3. `POST /wallets` with `currency=EUR` → `422`
     (`Input should be 'UZS' or 'USD'`).
  4. `PATCH /wallets/{id}` with `currency` field → `422`
     (`extra_forbidden`), confirming currency is immutable after creation.
  5. Member role → `403` on wallet `POST`/`PATCH`/`DELETE`.
  6. Owner created a top-level expense category and a subcategory with
     correct `parent_id` linkage.
  7. Deleting an income category with one linked transaction (inserted
     directly via SQLAlchemy session) returned
     `affected_transactions_count == 1`; the transaction itself
     remained `is_deleted == False` and kept its category reference,
     confirming no cascade to `transactions`.
  8. Deleting a top-level expense category with one subcategory
     cascaded `is_deleted = true` to the subcategory in the same
     operation.
  9. `POST /categories/expense` with `parent_id` pointing at a
     subcategory → `400`, confirming 2-level nesting is rejected.
  Cross-family 404 behavior (wallets and categories) was not
  re-verified manually — already covered by
  `test_cross_family_wallet_access_returns_404` and
  `test_cross_family_category_access_returns_404` in
  `backend/tests/test_wallets_categories.py` (11/11 passing).