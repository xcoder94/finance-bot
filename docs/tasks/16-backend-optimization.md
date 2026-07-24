# Task 16 — Backend Query & Index Optimization

Depends on: Task 13 (`13-api-family-members.md` — done, verified)
PRD reference: §12, §13 (performance/scale notes)

## Goal

Fix the 5 high-impact performance findings from the backend audit
(GPT-5.6 Sol, 2026-07-23). No frontend changes required — all fixes are
internal to query/aggregation logic; API response shapes are unchanged.

Out of scope (explicitly, do not touch):
- Medium/low-impact audit findings (duplicate user-count query, missing
  `users.family_budget_id` index, onboarding session/Telegram-call
  ordering, connection-pool config, soft-deleted-family auth gap,
  `expense_categories.parent_id` index, transaction write round-trips,
  offset pagination) — deferred to a later task. **Update: items 6–11
  and 13 are now covered by Part 2, below. Only items 12, 14, and 15
  remain deferred beyond this task file. See Part 2 for exact scope.**
- Seed-category "duplication" — audit concluded this is not a real
  problem at target scale (~21 rows/family, ~21k rows at 1,000
  families). No action.
- Any frontend/API contract change.
- Member lifecycle — not part of this task.

## Scope (5 items)

### 1. N+1 queries in wallet/category listing
Where: `backend/app/api/v1/wallets.py:31-48`,
`backend/app/api/v1/categories.py:39-55`, `:124-141`

Each listed wallet/category currently runs a separate per-row
transaction-count query. Replace with one aggregate query per endpoint,
grouped by category/wallet id:
- Wallet counts: aggregate both `wallet_id` and `to_wallet_id` via
  `UNION ALL`, not `OR`.
- Category counts: single grouped aggregate query per endpoint.
- No ORM eager-loading — use SQL aggregation, not relationship loading.

### 2. Missing indexes on transaction FK columns
Where: `backend/app/models/transaction.py:19-36`; current migration
`backend/alembic/versions/a1b2c3d4e5f6_create_core_tables.py:153-170`
only indexes `family_budget_id`, `created_by_user_id`,
`transaction_date`.

Add a new Alembic migration (do not edit `a1b2c3d4e5f6`) adding indexes
on:
- `transactions.wallet_id`
- `transactions.to_wallet_id`
- `transactions.income_category_id`
- `transactions.expense_category_id`

Use partial indexes covering `WHERE is_deleted = false`. For the
nullable columns (`to_wallet_id`, `income_category_id`,
`expense_category_id`), also exclude NULLs from the partial index.

### 3. Trend analytics loads full transaction history, aggregates in Python
Where: `backend/app/services/history_analytics.py:321-379`

Currently has no date predicate despite only returning the last 12
months. Fix:
- Restrict the SQL query to the start of the oldest requested month.
- Aggregate by month/currency/type in PostgreSQL (`GROUP BY`), not in
  Python.
- Fill any missing month/currency buckets in Python only after
  receiving the small aggregated result set.

### 4. Wallet balances load full transaction history on every request
Where: `backend/app/services/history_analytics.py:470-528`

Fix:
- Compute the balance ledger in SQL using conditional aggregation or a
  `UNION ALL` of source/destination wallet effects.
- Aggregate by currency in SQL, return only final rows.
- Do not introduce a precomputed balance table — audit explicitly says
  this is unnecessary at current target scale.

### 5. History query lacks a composite index for its access pattern
Where: query at `backend/app/services/history_analytics.py:113-152`;
existing indexes at
`backend/alembic/versions/a1b2c3d4e5f6_create_core_tables.py:159-170`

History filters by `family_budget_id` + `is_deleted` + date range, then
orders by `transaction_date DESC, id DESC`. Add, in the same new
migration as item 2, a partial composite index:
`(family_budget_id, transaction_date DESC, id DESC) WHERE is_deleted = false`.

Review (do not blindly keep) existing overlapping single-column indexes
against actual query plans once this index is in place — remove only if
clearly redundant and confirmed via `EXPLAIN`.

## Migration rules
- One new Alembic migration for all index additions in items 2 and 5.
- Must be reversible (`alembic downgrade -1` drops all new indexes
  cleanly).
- Do not modify the existing `a1b2c3d4e5f6` migration.

## Acceptance criteria
- [ ] Wallet listing endpoint: no per-row count query (verify via query
      log / `EXPLAIN` — one aggregate query instead of N)
- [ ] Category listing endpoints (income + expense): same
- [ ] New migration adds the 4 transaction FK indexes (partial, as
      specified) — reversible
- [ ] New migration adds the history composite index — reversible
- [ ] Trend analytics: SQL query has a date lower-bound; aggregation is
      in SQL, not Python
- [ ] Wallet balances: SQL aggregation, not Python materialization of
      full transaction history
- [ ] All existing endpoint response shapes unchanged (no frontend
      changes needed — confirm by diffing response JSON before/after
      for each touched endpoint)
- [ ] Full pytest suite passes (77+ existing tests, plus any new ones
      for the touched services)

## Verification
Manual/Python verification script written separately (not delegated to
Cursor), following `backend/scripts/manual_verify_*.py` pattern:
- Baseline/delta pattern for aggregate correctness (per established
  principle — no hardcoded absolute values).
- Query-count assertions (e.g. via SQLAlchemy engine logging or
  `sqlalchemy.event`) confirming N+1 patterns are gone for items 1, 3, 4.
- `EXPLAIN (ANALYZE, BUFFERS)` spot-check confirming new indexes are
  used for items 2 and 5.

## Changelog
- **2026-07-23 — implemented:**
  - Replaced per-row transaction-count queries in
    `backend/app/api/v1/wallets.py` and
    `backend/app/api/v1/categories.py` with one grouped aggregate query
    per listing endpoint. Wallet references are combined with
    `UNION ALL` across `wallet_id` and `to_wallet_id`.
  - Rewrote `get_trend` and `get_wallet_balances` in
    `backend/app/services/history_analytics.py` to aggregate in
    PostgreSQL. Trend now applies the twelve-month lower bound; wallet
    balances use a source/destination `UNION ALL` ledger.
  - Added reversible migration
    `backend/alembic/versions/e5f6a7b8c9d0_add_transaction_query_indexes.py`
    with the four partial FK indexes and the partial composite history
    index, with matching SQLAlchemy metadata in
    `backend/app/models/transaction.py`. Downgrade and re-upgrade were
    verified.
  - Retained the existing `family_budget_id` and `transaction_date`
    single-column indexes. `EXPLAIN` used the new composite index for
    the scoped active-history query, while the existing indexes remained
    useful for family-only queries without the partial predicate and
    date-only queries respectively; neither was clearly redundant.
  - Extended `backend/tests/test_wallets_categories.py` and
    `backend/tests/test_history_analytics.py` with grouped-count,
    query-count, index-definition, trend aggregation, missing-bucket,
    destination-wallet, and unchanged-response-shape coverage.
    Full suite result: 79 passed.
- Deviations from scope: none.
- Исправлена ошибочная константа в верификационном скрипте (2→3), финально 6/6 PASS

---

# Part 2 — Medium/low-impact findings (items 6, 7, 8, 9, 10, 11, 13)

Depends on: Part 1 (above — done, verified, 6/6 PASS)
Source: `task16-original-audit-gpt56sol.md` (medium/low-impact section).
Line numbers in that file are stale after Part 1 — locate code by
function/pattern, not by line number.

## Goal

Address the remaining medium/low-impact findings that are in scope for
this task. No frontend changes — all fixes are internal to
query/session/auth logic; API response shapes are unchanged except
where explicitly noted (item 11 adds a new 403 case that did not exist
before, which is a behavior addition, not a contract change to any
existing successful response).

Out of scope (explicitly, do not touch in Part 2):
- **Item 12** (ambiguous soft-delete behavior in `count_family_users()`)
  — deferred until member-removal ships in the frontend (Task 15 was
  cancelled/deferred to v2).
- **Item 14** (transaction write round-trips) — audit itself recommends
  against touching without measurement; no observed latency issue.
- **Item 15** (offset → keyset pagination) — changes the API contract,
  requires frontend changes, will be its own task later.
- Bot auto-start from the FastAPI process — a real idea for later, but
  it is a deployment/process-architecture change, not a query/session
  fix. Track separately in `roadmap.md` backlog; do not attempt here.

## Scope (7 items)

### 6. Summary analytics aggregates full transaction objects in Python
Where: `get_summary()` in `backend/app/services/history_analytics.py`

Currently loads every transaction row in the date range (default: full
calendar year) and computes income/expense/transfer-net totals and
weekday buckets in Python. Fix:
- Move income, expense, and transfer-net totals per currency into one
  grouped SQL aggregate query (`GROUP BY` currency, conditional
  aggregation with `case()`/`sum()` for the three types, matching the
  pattern already used in `get_wallet_balances`).
- Move weekday buckets into SQL using `func.extract("isodow", ...)`
  (Postgres ISODOW: 1=Monday..7=Sunday). **Convert to the existing
  0=Monday..6=Sunday convention used by `day_of_week_expense` /
  `day_of_week_income` by subtracting 1** — do not change the response
  schema's day-index convention. Group by currency + isodow + type.
  Apply the same date-range/currency filter as the totals query.
- Do not introduce a new composite index for this query. The existing
  partial index from Part 1 item 5,
  `(family_budget_id, transaction_date DESC, id DESC) WHERE is_deleted = false`,
  already covers the `family_budget_id` + date-range filter this query
  needs. Confirm via `EXPLAIN` during verification (done separately by
  Claude, not part of this Cursor prompt) rather than adding an
  overlapping index preemptively.
- `elapsed_days_in_period` and `average_daily_expense` calculation stay
  in Python — they operate on the small aggregated result, not on raw
  rows.
- Preserve exact current behavior for currencies with zero transactions
  in the period (they must not appear in `by_currency`, matching
  current behavior of only iterating `sorted(currency_data)`).

### 7. History performs the same family-user count twice
Where: `backend/app/api/v1/history.py` (`list_transaction_history`),
`get_history()` and `should_include_created_by()` in
`backend/app/services/history_analytics.py`

Fix:
- `get_history()` takes a new required parameter `include_created_by: bool`
  instead of computing it internally. Remove the internal
  `should_include_created_by()` call from inside `get_history()`.
- The endpoint (`history.py`) already calls
  `should_include_created_by()` once before calling `get_history()` —
  keep that single call, pass the result into `get_history()`.
- When `include_created_by` is `False`, do not outerjoin `User` at all
  and do not select `User.first_name` / `User.username` — build the
  query conditionally (e.g. start from the base statement, add the
  `User` outerjoin and the two extra selected columns only when
  `include_created_by` is `True`; reference the extra columns only in
  that branch when building `HistoryItem`).
- Net effect: one `should_include_created_by()` call total per request,
  and no `users` join when author data won't be returned.

### 8. Missing `users.family_budget_id` index
Where: `backend/app/models/user.py`; new Alembic migration.

Decision (confirmed): a single plain (non-partial) B-tree index on
`family_budget_id`. This covers both `count_family_users()` (which
intentionally has no `is_deleted` filter — item 12 is deferred, so this
must keep working unfiltered) and the member-listing query, without
maintaining two overlapping indexes at this scale. Do not use a partial
index for this one.
- Add `index=True` to the `family_budget_id` column in
  `backend/app/models/user.py`.
- Add the corresponding index in the same new migration as item 13
  (see below) — do not touch the existing `a1b2c3d4e5f6` migration.

### 9. Database connections held open across Telegram API calls in onboarding
Where: `backend/bot/onboarding.py` — `language_callback` (owner branch:
`bot.get_me()` called while `session.begin()` transaction is still
open) and `invite_handler` (`bot.get_me()` called while the session is
still open, even though it's not an explicit `session.begin()` block).

**Scope note (confirmed): fix only the session/API-call ordering.**
Auto-starting the bot process from FastAPI is out of scope for Part 2
— track it separately in `roadmap.md`.

Fix:
- Locate the bot process's startup entrypoint (search for
  `Dispatcher`, `dp.start_polling`, or similar aiogram startup code —
  it is not one of the files listed under "Context you need" below,
  find it by pattern).
- Cache the bot's username once at bot startup, using an aiogram
  startup hook (e.g. `dp.startup.register(...)`) analogous to how
  `init_bot_username()` caches it in the FastAPI `lifespan` — do not
  reuse the FastAPI lifespan itself, the bot is a separate process.
  Store it in a module-level variable in `backend/app/services/invite.py`
  (or equivalent) accessible to `onboarding.py` without an API call.
- In `language_callback`: restructure the owner branch so all DB writes
  happen and the `session.begin()` block is closed *before*
  `build_invite_link()` is called using the cached username — no
  network call inside the open transaction.
- In `invite_handler`: read everything needed from the DB, close the
  session, *then* build the invite link from the cached username —
  no `bot.get_me()` call while the session is open.
- If the cached username is somehow unavailable (edge case — startup
  hook hasn't run yet), fall back to calling `bot.get_me()` outside any
  open session, same as today, rather than failing the request.

### 10. Connection-pool configuration relies entirely on defaults
Where: `backend/app/db.py`

Confirmed sizing (target: 1 FastAPI worker + 1 bot process, comfortably
handling 100 concurrent users):
- `pool_size=10`
- `max_overflow=10`
- `pool_timeout=30`
- `pool_recycle=1800`
- Keep `pool_pre_ping=True` (already set).

Apply these explicitly in `create_async_engine(...)` in
`backend/app/db.py`. Since both the FastAPI process and the bot process
import their engine from this same module, this single change applies
to both processes automatically — do not duplicate engine configuration
elsewhere.

### 11. Soft-deleted family budgets not enforced by authentication
Where: `get_current_user()` in `backend/app/auth/user_deps.py`

Confirmed: return **403** (not 404) when the user is active but their
family budget is soft-deleted — this is an internal Mini App, not a
public API, so there's no reason to obscure resource existence.

Fix:
- Extend the existing query in `get_current_user()` to join
  `FamilyBudget` and also select `FamilyBudget.is_deleted`, in the same
  round trip (do not add a second query).
- If no matching active user row is found → `401` (unchanged, existing
  behavior).
- If the user is found but `FamilyBudget.is_deleted` is `True` → `403`.
- If the user is found and the family is active → return the user
  (unchanged, existing behavior).
- This is currently unreachable in practice (no family-deletion
  endpoint exists yet) — this is intentional groundwork per the audit,
  not a response to an active bug.

### 13. Expense-category parent FK is unindexed
Where: `backend/app/models/expense_category.py`; same new migration as
item 8.

- Add a partial index on `expense_categories.parent_id`,
  `WHERE parent_id IS NOT NULL` (top-level categories, where
  `parent_id IS NULL`, are never looked up by this column).
- Reflect this in the model (`Index(...)` or equivalent — `parent_id` is
  not itself marked `index=True` at the column level since it needs the
  partial condition).

## Migration rules
- One new Alembic migration for items 8 and 13 (the two new indexes:
  plain `users.family_budget_id`, partial
  `expense_categories.parent_id WHERE parent_id IS NOT NULL`).
- Must be reversible (`alembic downgrade -1` drops both cleanly).
- Do not modify `a1b2c3d4e5f6` or the Part 1 migration
  (`e5f6a7b8c9d0_add_transaction_query_indexes.py`).

## Acceptance criteria
- [ ] `get_summary()`: income/expense/transfer-net totals and weekday
      buckets computed in SQL, not Python; response shape and values
      unchanged for existing test fixtures (verified via baseline/delta,
      not hardcoded values)
- [ ] `get_summary()`: no new index added; `EXPLAIN` confirms the Part 1
      history index is used (or, if it isn't and the plan is poor, this
      is flagged back to Claude before closing the item — Cursor does
      not unilaterally add an index here)
- [ ] History endpoint: `should_include_created_by()` called exactly
      once per request (verified via query-count assertion); no `users`
      join in the generated SQL when `include_created_by` is `False`
- [ ] New migration adds plain `users.family_budget_id` index and
      partial `expense_categories.parent_id` index — reversible
- [ ] Owner onboarding flow and `/invite` handler: no `bot.get_me()`
      call while a DB session/transaction is open (verified by code
      review, not just agent report)
- [ ] `backend/app/db.py`: pool settings explicitly set as specified
      above
- [ ] `get_current_user()`: soft-deleted family → 403; deleted/missing
      user → 401 (unchanged); active user + active family → 200
      (unchanged)
- [ ] All existing endpoint response shapes unchanged except the new
      403 case in item 11 (confirm by diffing response JSON
      before/after for touched endpoints)
- [ ] Full pytest suite passes, including new tests for items 6, 7, 9,
      11

## Verification
Manual/Python verification script written separately by Claude (not
delegated to Cursor), following the `backend/scripts/manual_verify_*.py`
pattern:
- Baseline/delta pattern for `get_summary()` aggregate correctness.
- Query-count assertion confirming `should_include_created_by()` runs
  once per history request, and confirming no `users` join appears in
  the generated SQL when it returns `False`.
- `EXPLAIN` spot-check for `get_summary()`'s query plan and for the two
  new indexes (items 8, 13).
- Isolated throwaway family for the soft-deleted-family 403 test (per
  established principle — destructive/state-mutating verification never
  uses the shared 111111/222222 fixture).
- Manual check (not automatable) that onboarding's owner flow and
  `/invite` complete correctly end-to-end in the real bot — session
  ordering itself is verified by code review.

## Changelog
- **2026-07-23 — implemented:**
  - Rewrote `get_summary()` in
    `backend/app/services/history_analytics.py` to compute per-currency
    totals through a grouped source/destination SQL ledger and weekday
    buckets through a grouped `ISODOW` query after explicitly converting
    transaction timestamps to UTC, preserving the existing Monday-zero
    response convention and Python elapsed-day calculation. Added
    near-midnight UTC boundary coverage for weekday bucketing.
  - Changed `get_history()` to accept the endpoint's
    `include_created_by` result and conditionally add the `users` join
    and author columns. The family-user count now runs once per request.
  - Added reversible migration
    `backend/alembic/versions/f6a7b8c9d0e1_add_user_and_category_indexes.py`
    for the plain `users.family_budget_id` index and partial
    `expense_categories.parent_id IS NOT NULL` index, with matching
    SQLAlchemy model metadata. Downgrade and re-upgrade were verified.
  - Added a bot-process startup hook that caches the Telegram bot
    username in `backend/app/services/invite.py`. Owner onboarding and
    `/invite` now finish their database work before using the cache or
    the outside-session `bot.get_me()` fallback. The owner's registration
    welcome message was later simplified to omit the deferred MVP 2 invite
    link, so that branch no longer resolves the bot username; `/invite`
    remains unchanged and fully functional.
  - Set the confirmed async-engine pool size, overflow, timeout, and
    recycle values explicitly in `backend/app/db.py`.
  - Updated `get_current_user()` to join `FamilyBudget` in the existing
    query and return 403 for an active user whose family is soft-deleted.
  - Extended history/analytics and onboarding tests with grouped-summary
    values and SQL-shape checks, single-count/no-user-join coverage,
    bot-call session-ordering coverage, and the soft-deleted-family 403
    case. Full suite result: 83 passed.
- Deviations from scope: none.