# Roadmap — Family Finance Tracker

Reference: `docs/PRD.md` (v1.0, finalized).
This document breaks the PRD into build phases and maps each phase to task files in `docs/tasks/`.

## Phase 0 — Repo, tooling & runnable skeleton (in progress)

- [x] Monorepo structure: `backend/`, `frontend/`, `shared/`, `docs/`
- [x] `AGENTS.md` / `CLAUDE.md` setup
- [x] `frontend/`: `npm install` done, confirm Oxlint config, confirm `@tma.js/sdk-react`, Zustand wired in
- [x] `.cursor/rules`
- [x] `00-local-env.md` — local Postgres running, empty FastAPI app responding on `/health`, empty Aiogram bot responding to `/start` with "pong". No real logic yet — this is the skeleton every later task runs inside.

No PRD section — infrastructure only. **This task moved earlier on purpose**: every task from 01 onward must be runnable and manually verifiable the moment it's done, not just at the end.

## Phase 1 — MVP

Goal: one Family Budget, Owner + Members, full income/expense/transfer tracking, history, analytics, settings — running locally.

**Rule for every task file below**: each one ends with a "Проверка" (verification) section — concrete steps to run the app and confirm the feature works, before moving to the next task. No task is "done" until it has been run and checked, not just written.

| # | Task file | PRD section(s) | Scope | Проверка (as you build) |
|---|---|---|---|---|
| 01 | ✅ `01-auth-telegram.md` | §10 (Security) | Telegram `initData` HMAC-SHA256 validation on every API request | Done — 10/10 unit tests pass; protected test endpoint returns 401 on bad `initData`, 200 on valid. Fixed 2026-07-18 (`GET /api/v1/me` now returns `role`/`family_budget_id`/`language`), verified via `manual_verify_me_endpoint.py`, 18/18 PASS |
| 02 | ✅ `02-db-schema.md` | §2, §5, §6, §8, §9, §10 | Tables: `family_budgets`, `users`, `wallets`, `income_categories`, `expense_categories`, `transactions`; seed expense categories from user's spreadsheet | Done — schema verified manually via `psql` (columns, types, FKs, indexes); one bug found and fixed (`expense_categories.parent_id` was NOT NULL, corrected to nullable via follow-up migration `96192ca13fd1`) |
| 03 | ✅ `03-bot-onboarding.md` | §3, §8 | ... | Done — verified end-to-end in Telegram: Owner flow, Member flow via real second account, seed data copy, invalid-token handling, repeat-/start idempotency all confirmed; 7/7 unit tests pass |
| 04 | ✅ `04-api-wallets-categories.md` | §4.7, §5, §7 | CRUD for wallets and categories (Owner-only), delete-confirmation logic (§7) | Done — verified via `manual_verify_categories.py`, 12/12 PASS |
| 05 | ✅ `05-api-transactions.md` | §4.2–§4.4, §6 | Income/Expense/Transfer endpoints, role-based edit/delete rules, rate-direction logic | Done — verified via `manual_verify_transactions.py`, 30/30 PASS |
| 06 | ✅ `06-api-history-analytics.md` | §4.5, §4.6 | History endpoint with filters; analytics endpoints | Done — verified via `manual_verify_history_analytics.py`, 36/36 PASS. Currency-scoping fix (2026-07-18), verified via `manual_verify_currency_scoping.py`, 14/14 PASS |
| 07 | ✅ `07-frontend-shell.md` | §4.1, §9 | App shell, routing, Zustand store structure, `react-i18next`, TelegramUI base layout | Done — verified manually in browser, all Verification steps confirmed (splash→shell, 4 routes, lazy-loaded Analytics chunk, language switch, 401/403/404/network error screens, prod build clean of dev token). 5 bugs found and fixed during this verification session |
| 08 | ✅ `08-api-wallet-balances.md` | §4.1, §6 | New read-only endpoint: accumulated per-currency wallet balance (all-time, active + soft-deleted wallets), for Home screen summary | Automated `manual_verify_wallet_balances.py` (baseline/delta pattern) |
| 09 | ✅ `09-frontend-home.md` | §4.1 | Home screen: month selector, per-currency summary (income/expense from Task 06 `summary`, balance from Task 08 `wallet-balances`), quick actions, recent transactions | Home screen shows real data from backend for a test Family Budget |
| 10 | ✅ `10-frontend-add-transaction.md` | §4.2–§4.4 | Add Income / Add Expense / Add Transfer forms, live calculator | Add one real transaction of each type through the UI, confirm it appears in DB and updates Home summary |
| 11 | ✅ `11-frontend-history.md` | §4.5 | History table, filters (month + custom range), color coding, per-row edit/delete (Part 2, same task file, no separate task number) | Done — Part 1 (view: filters, dual-currency totals, list, pagination) and Part 2 (edit/delete via existing `PATCH`/`DELETE /transactions/{id}`, role-based visibility) both manually verified in browser. Addendum: Home's Recent Transactions list updated to also distinguish "Перевод" vs "Обмен валюты" (was Task 11 scope from the start, missed in first pass, fixed same day) |
| 12 | ✅ `12-frontend-analytics.md` | §4.6 | Charts (donut, bar/line), lazy-loaded per NFR in §10 | Charts render with seeded data, Analytics screen doesn't block initial app load (lazy-load confirmed in Network tab) |
| 13 | ✅ `13-api-family-members.md` | §3, §8 | HTTP API for listing members, invite-link retrieval/regeneration, member removal — previously bot-only | Done — verified via `manual_verify_members.py`, 21/21 PASS. Bot username cached at FastAPI startup (`lifespan`) instead of a Telegram API call per request. Existing bot `/start`/`/invite` flow unaffected — `test_onboarding.py` still 7/7 pass |
| 14 | ✅ `14-frontend-settings.md` | §4.7, §8 | Category/wallet management UI, member management, language selector | Owner creates a category and a wallet through UI, generates invite link, confirms it works end-to-end |
| 15 | ❌ CANCELLED (2026-07-23) | §8 | Member management UI (regenerate invite link, remove member) descoped from MVP — unclear real demand for multi-user families yet, may revisit in v2. Backend (Task 13) and display-only frontend (Task 14) remain in place as foundation. | — |
| 16 | ✅ `16-backend-optimization.md` (Part 1) | §12, §13 | Backend audit (GPT-5.6 Sol) + fix for 5 high-impact findings: N+1 queries in wallet/category listing endpoints, missing indexes on `transactions` FK columns, trend/wallet-balance aggregation moved from Python to SQL, composite index for history query pattern. Seed-category duplication concern investigated and ruled out as non-issue at target scale (~1,000 families). Part 2 (medium/low-impact findings) pending, separate scope within same task file | Done — verified via `manual_verify_task16_optimization.py` (baseline/delta, query-count assertions, EXPLAIN index checks, trend month-boundary and timezone checks), 6/6 PASS |
| 17 | ✅ `17-frontend-ux-audit.md` | §4.1–§4.7, §9, §10 | Three-part frontend UX/UI audit remediation: navigation/icons/theme/progressive Analytics rendering; hierarchy/control sizing/caching/layout; localization/accessibility/metadata and functional bug fixes | Done — all three parts implemented; `npm run build` and `npm run lint` pass (two pre-existing Fast Refresh warnings). Real-Telegram final verification and screenshots pending |

## Phase 2 — v2 (post-MVP, not started until Phase 1 is complete and in use)

From PRD §11 "Out of scope for MVP":

- Admin panel for multiple Family Budgets (schema-ready via `role` field)
- Automatic exchange-rate fetching (replacing manual rate entry)
- Budgets / spending limits per category
- Report export (PDF/Excel)
- Push notifications / reminders
- Per-member analytics breakdown (no schema blocker — `created_by_user_id` already stored)
- "≈ total in USD" informational line (§6, explicitly optional/future)

## Phase 3 — v3 (later, unscheduled)

- Member-specific private wallets (currently: all wallets shared, by design)
- Hosting/deployment strategy (local-first is deliberate for MVP, §10)
- Two-level income categories (schema already supports via `parent_id`, no migration needed)

## Notes

- Task numbering is sequential build order, not strict PRD section order — some tasks bundle multiple PRD sections where they share a data model or screen.
- Each task file should be self-contained enough for a code-generation agent to execute without re-reading the full PRD, per the existing convention for `01-auth-telegram.md`.
- Documentation language: English (per PRD §12 resolved-decisions log).