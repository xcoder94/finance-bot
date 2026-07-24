# Task 16 — Summary (done, 2026-07-23)

Backend query/index optimization based on GPT-5.6 Sol audit
(`task16-original-audit-gpt56sol.md`). Full details and per-item specs
live in `docs/tasks/16-backend-optimization.md` (Part 1 + Part 2) — this
file is a condensed pointer for other chats, not a replacement for it.

## Status: Task 16 closed. All in-scope audit items (1–11, 13) done.
Items 12, 14, 15 explicitly deferred (see "Deferred" below).

## Part 1 — High impact (items 1–5)
Verified 6/6 PASS via `manual_verify_task16_optimization.py`.
- N+1 fixed in wallet/category listing endpoints (aggregate queries).
- New migration `e5f6a7b8c9d0_add_transaction_query_indexes.py`: partial
  indexes on `transactions.wallet_id`, `to_wallet_id`,
  `income_category_id`, `expense_category_id`, plus composite
  `(family_budget_id, transaction_date DESC, id DESC) WHERE is_deleted = false`.
- `get_trend()` and `get_wallet_balances()` in `history_analytics.py`
  rewritten to aggregate in SQL instead of Python.

## Part 2 — Medium/low impact (items 6, 7, 8, 9, 10, 11, 13)
Verified 19/19 PASS via `manual_verify_task16_part2.py`. Full pytest
suite: 83+ passed throughout.

- **Item 6**: `get_summary()` rewritten to aggregate income/expense/
  transfer-net and weekday buckets in SQL (was full Python iteration).
  Weekday uses `EXTRACT(ISODOW FROM TIMEZONE('UTC', transaction_date))`
  — explicitly UTC-pinned, not dependent on Postgres session timezone
  (bug caught and fixed during review). No new index added — existing
  Part 1 composite index covers it; `EXPLAIN` at low row counts may
  legitimately pick the plainer `family_budget_id` index instead
  (informational, not a defect — re-check at real data volume).
- **Item 7**: `get_history()` now takes `include_created_by: bool` as a
  parameter instead of computing it twice; `users` join is skipped
  entirely when author data won't be returned.
- **Item 8**: single plain (non-partial) B-tree index on
  `users.family_budget_id` — chosen over a partial index because
  `count_family_users()` intentionally has no `is_deleted` filter
  (item 12 deferred) and must keep working unfiltered; one index
  serves both that query and member listing at this scale.
- **Item 9**: bot username is now cached once (aiogram `dp.startup`
  hook in `backend/bot/main.py`, shared cache in
  `app/services/invite.py`) instead of calling `bot.get_me()` inside an
  open DB session/transaction. Fixed in both `language_callback` (owner
  branch) and `invite_handler` (`/invite`). Covered by two automated
  tests asserting the DB session is closed before the Telegram API call
  (`TestInviteHandlerSessionOrdering`,
  `TestLanguageCallbackSessionOrdering`).
- **Item 10**: connection pool explicit in `backend/app/db.py`:
  `pool_size=10, max_overflow=10, pool_timeout=30, pool_recycle=1800,
  pool_pre_ping=True`. Sized for confirmed target: 1 FastAPI worker +
  1 bot process, 100 concurrent users.
- **Item 11**: `get_current_user()` in `user_deps.py` now joins
  `FamilyBudget` in the same query — returns 401 if no active user,
  **403** if the user is active but their family is soft-deleted
  (new behavior; currently unreachable in practice, no family-deletion
  endpoint exists yet — groundwork for later).
- **Item 13**: partial index on `expense_categories.parent_id WHERE
  parent_id IS NOT NULL`. Same migration as item 8:
  `f6a7b8c9d0e1_add_user_and_category_indexes.py`.

### Scope addition (not from the original audit)
Owner's welcome message on `/start` no longer includes the invite link
(`MESSAGES["welcome_owner"]` in `onboarding.py`). Family/invite/roles
functionality itself is **not removed** — `/invite` command still works
exactly as before, this is deferred to MVP 2's UI, not descoped. This
was a same-session addition to Task 16 Part 2, not a separate task,
per the "mini-fixes found before a task closes are part of that task"
convention.

## Deferred (explicitly out of scope, not part of Task 16)
- **Item 12** — `count_family_users()` ambiguous soft-delete behavior.
  Revisit only when member removal (Task 15, cancelled/deferred to v2)
  ships in the frontend.
- **Item 14** — transaction write round-trips. Audit itself recommends
  against touching without measurement; no observed issue.
- **Item 15** — offset → keyset pagination for history. Changes the API
  contract, needs frontend changes too; separate future task.
- **Bot auto-start from the FastAPI process** — raised during Part 2
  discussion (would let the bot start automatically alongside the
  backend instead of being launched separately). Real idea, but a
  deployment/process-architecture change, not a query/session fix —
  tracked in `roadmap.md` backlog, not attempted in Task 16.

## Files touched (Part 2)
`backend/app/services/history_analytics.py`,
`backend/app/api/v1/history.py`,
`backend/app/models/user.py`,
`backend/app/models/expense_category.py`,
`backend/app/auth/user_deps.py`,
`backend/app/db.py`,
`backend/app/services/invite.py`,
`backend/app/api/v1/members.py`,
`backend/bot/main.py`,
`backend/bot/onboarding.py`,
`backend/alembic/versions/f6a7b8c9d0e1_add_user_and_category_indexes.py`,
`backend/tests/test_history_analytics.py`,
`backend/tests/test_onboarding.py`.

## Verification
- `backend/scripts/manual_verify_task16_optimization.py` — Part 1, 6/6 PASS.
- `backend/scripts/manual_verify_task16_part2.py` — Part 2, 19/19 PASS.
- Full pytest suite passing throughout (83+ tests after Part 2).
- Manual real-bot verification of the onboarding welcome-message change
  was skipped (no second Telegram account available) — covered instead
  by code review + the automated session-ordering tests above.

## Roadmap
`roadmap.md` updated manually by the user — not reflected in this file,
check `roadmap.md` directly for current task numbering/status.

## Next
Task 17 — frontend audit. Being started in a new chat.
