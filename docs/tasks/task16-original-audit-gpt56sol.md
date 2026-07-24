# Backend audit — GPT-5.6 Sol, 2026-07-23

Original audit findings, produced before Task 16 Part 1 implementation.
Part 1 (items 1–5, "High impact") is already implemented and verified
(6/6 PASS) — do not redo. Line numbers below are stale after Part 1's
changes; locate code by function/pattern, not by line number.

## High impact — DONE (Part 1, do not redo)

1. Category and wallet listing endpoints have explicit N+1 queries
2. Frequently queried transaction foreign keys have no indexes
3. Trend analytics reads all historical transactions and aggregates in Python
4. Wallet balances read and materialize every historical transaction on every request
5. History lacks an index matching its principal access pattern

## Medium impact — SCOPE FOR PART 2 (items 6, 7, 8, 9, 10, 11)

6. Summary analytics also aggregates full transaction objects in Python

Where (stale): `backend/app/services/history_analytics.py:382-464`

Unlike trend, this query has a date range, so growth is bounded by the
requested period. However, the default is a full calendar year and each
row is still transferred and instantiated before totals and weekday
buckets are computed.

Recommendation:
- Move income, expense, transfer-net, and weekday aggregation into SQL.
- Consider a composite partial index such as `(family_budget_id, type, transaction_date) WHERE is_deleted = false`, but test whether the history index already gives adequate plans before adding another large overlapping index.

7. History performs the same family-user count twice

Where (stale):
- First call: `backend/app/api/v1/history.py:26`
- Second call inside `get_history`: `backend/app/services/history_analytics.py:111`

Including authentication, a history request currently performs:
- current-user lookup
- first user count
- duplicate user count
- transaction count
- history-row query

Recommendation:
- Determine the author-display decision once and pass it into the history service, or return that decision with the service result.
- Avoid joining `users` when author data will not be returned.

8. Missing `users.family_budget_id` index

Where (stale):
- Model: `backend/app/models/user.py:14-16`
- Migration has no corresponding index.

It affects:
- member listing: `backend/app/api/v1/members.py:83-91`
- history's family-user count: `backend/app/services/history_analytics.py:50-55`

A few thousand users would still be manageable, but this contradicts the PRD requirement that family/user scoping columns be indexed and will become unnecessary global scanning.

Recommendation:
- Add an index beginning with `family_budget_id`.
- A partial composite `(family_budget_id, created_at) WHERE is_deleted = false` fits active member listing.
- If historical/removed users must be counted, preserve an index usable without the partial condition.

9. Database connections are held across Telegram network calls in onboarding

Where (stale):
- Owner callback opens `session.begin()` and then calls `bot.get_me()`: `backend/bot/onboarding.py:248-290`
- `/invite` calls `bot.get_me()` while its DB session remains open: `backend/bot/onboarding.py:301-319`
- Some error replies are also awaited before closing the session: `backend/bot/onboarding.py:206-220`

The owner callback is most important: it holds an active database transaction while waiting on an external API. Under network delay, this unnecessarily occupies a pooled connection and prolongs transaction lifetime.

Recommendation:
- Cache/configure the bot username as the FastAPI members API already does.
- Finish or release database work before sending Telegram requests.
- Keep external I/O outside database transaction scopes.

10. Connection-pool configuration relies entirely on defaults

Where (stale): `backend/app/db.py:7-8`

There are no session leaks in FastAPI: `get_session()` uses `async with`, and FastAPI dependency caching means authentication and endpoint logic normally share one request session.

However, engine defaults are effectively pool size 5 plus 10 overflow connections per process. Multiple API workers plus the bot process multiply that number. No explicit timeout/recycle policy documents the production capacity model.

Recommendation:
- Configure pool size, overflow, timeout, and possibly recycle explicitly for deployment.
- Calculate the total as `(API workers + bot processes) × per-process pool limit` and keep it safely below PostgreSQL's connection allowance.
- `pool_pre_ping=True` is appropriate.
- Dispose the bot process's engine during graceful shutdown; FastAPI already disposes its engine in lifespan.

11. Soft-deleted family budgets are not enforced by general API authentication

Where (stale): `backend/app/auth/user_deps.py:12-23`

Authentication confirms only that the user is active. If a `FamilyBudget` is soft-deleted while its users remain active, those users can still reach wallet, category, transaction, history, analytics, and member endpoints.

Recommendation:
- Make the active-family invariant part of the current-user dependency or enforce that deleting a family also deactivates its users atomically.
- This is currently latent because there is no family-deletion endpoint, but it matters before a public/admin launch.

## Medium impact — EXPLICITLY DEFERRED, not in Part 2 scope

12. Active-user counting has ambiguous soft-delete behavior

Deferred: depends on member-removal being reachable through the product
UI, which it currently is not (Task 15, the removal UI, was cancelled/
deferred to v2). Revisit only when member removal ships.

Where (stale): `backend/app/services/history_analytics.py:50-55`

`count_family_users()` does not filter `User.is_deleted`. Consequently, a removed member permanently causes history to include author fields, even if only one active user remains.

This may be intentional because historical transactions should retain their author. If so, the function name and condition do not express that policy precisely; a removed member with no transactions also changes the response.

Recommendation (for when revisited):
- Decide whether the criterion is multiple active members, multiple historical authors, or simply always include author.
- If historical authors are intended, base it on distinct transaction authors in the relevant data rather than all user records.

## Low impact — EXPLICITLY DEFERRED, not in Part 2 scope

14. Transaction writes use several sequential validation round trips

Deferred: audit itself recommends against touching without measurement;
no observed latency issue at current scale.

Where (stale): `backend/app/services/transactions.py:57-129`

Income/expense validation performs two PK lookups; transfer validation performs two wallet lookups. Writes then commit and refresh. These are not N+1 patterns and are inexpensive at the expected write rate, but each create/update commonly uses several round trips.

Recommendation (for when revisited):
- Keep the validation because family and soft-delete checks are important.
- Optimize only if measured—for example, fetch both transfer wallets in one query. This is much lower priority than fixing read-side aggregation.

## Low impact — SCOPE FOR PART 2 (item 13 only)

13. Expense-category parent FK is unindexed

Where (stale): `backend/app/models/expense_category.py:17-19`

`parent_id` is queried when deleting a top-level category and during subcategory analytics. At only about 17 expense rows per family this is not currently meaningful, but indexing FKs is useful for referential checks and future hierarchy growth.

Recommendation:
- Low-priority index on `expense_categories.parent_id`, potentially partial where non-null.

## Low impact — NOT IN SCOPE for Part 2 (frontend contract change, separate task)

15. Deep offset pagination will eventually degrade

Where (stale): `backend/app/services/history_analytics.py:149-151`

Offset pagination is acceptable for MVP and modest histories, but large offsets require PostgreSQL to walk and discard preceding rows.

Recommendation (for a future, separate task, backend+frontend together):
- After adding the matching composite index, move to cursor/keyset pagination using `(transaction_date, id)` if families develop very long histories.
