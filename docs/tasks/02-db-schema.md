# Task 02 — Database Schema

Depends on: Task 01 (`01-auth-telegram.md` — done, verified)
PRD reference: §2, §3, §5, §6, §8, §9, §10, §12–13 (see PRD changelog, 2026-07-11)

## Goal

Create the initial Alembic migration defining all core tables for the MVP, plus a seed-data constant (used later in Task 03 onboarding, not created here) for default categories/wallets.

## Schema-wide decisions (confirmed 2026-07-11)

- **Primary keys: UUID**, not serial integers. Rationale: project will be deployed to a server shortly after local MVP validation; UUIDs avoid exposing sequential record counts and simplify merging/seeding data across environments later.
  - Implementation detail (not yet confirmed, using sensible default): generate UUIDs at the **application/ORM layer** (Python `uuid.uuid4()`, SQLAlchemy `default=uuid.uuid4`), not at the database layer. This avoids requiring the Postgres `pgcrypto` extension for `gen_random_uuid()`. Use this unless there's a reason to prefer DB-generated UUIDs.
- **Soft-delete everywhere.** Every table below gets:
  - `is_deleted` (boolean, not null, default `false`)
  - `deleted_at` (timestamptz, nullable)
  This replaces the earlier hard-delete-with-cascade design for categories/wallets (PRD §7, §4.7 — updated 2026-07-11) and generalizes the pattern already used for Member removal (PRD §8) to every entity, including `transactions` themselves (relevant for the Owner/Member delete-transaction permission in PRD §3).
  - **Application-level rule, not enforced by the migration itself:** every read query in later tasks (03–06) must filter `WHERE is_deleted = false` unless explicitly fetching deleted/archived records. This is a convention to carry forward, not something Alembic can enforce — flagging it now so it isn't missed in Task 04–06 queries.
- **Single Alembic migration** creating all 6 tables at once (confirmed — schema is being designed from scratch, no value in splitting into incremental migrations yet).

## Tables

### family_budgets
- `id` (UUID, PK)
- `is_deleted` (boolean, default false)
- `deleted_at` (timestamptz, nullable)
- `created_at` (timestamptz, default now)

### users
- `id` (UUID, PK)
- `telegram_id` (bigint, unique, indexed — the Telegram user id from initData)
- `family_budget_id` (UUID, FK → family_budgets.id, **not null**) — confirmed 2026-07-11: Task 01 (`auth-telegram`) does not read or write the `users` table at all, it only validates `initData`. The `users` row is created exclusively in Task 03 (`/start` handler), at which point `family_budget_id` and `role` are always known and set together (Owner: new `family_budgets` row created in the same flow; Member: resolved from the deep-link invite token). There is no intermediate state where a `users` row exists without a family — so this column must not be nullable.
- `role` (string: `"owner"` | `"member"`, **not null**) — Owner/Member role per PRD §3, set at creation time together with `family_budget_id` (see above — no nullable transitional state needed). Note: PRD §10 also mentions a separate future `role` field reserved for platform-level admin — do NOT conflate the two. This column is the Owner/Member role only. A platform-level role, if needed later, will be a separate column added in a future migration.
- `first_name` (string, nullable)
- `username` (string, nullable)
- `language` (string, default `"ru"`) — plain string per PRD §9, not an enum
- `is_deleted` (boolean, default false) — replaces the earlier `is_removed` naming, now consistent with every other table. This is the Member-removal soft-delete from PRD §8.
- `deleted_at` (timestamptz, nullable)
- `created_at` (timestamptz, default now)

### wallets
- `id` (UUID, PK)
- `family_budget_id` (UUID, FK → family_budgets.id, indexed, not null)
- `name` (string)
- `currency` (string, e.g. `"UZS"`, `"USD"`)
- `is_deleted` (boolean, default false)
- `deleted_at` (timestamptz, nullable)
- `created_at` (timestamptz, default now)

### income_categories
- `id` (UUID, PK)
- `family_budget_id` (UUID, FK → family_budgets.id, indexed, not null)
- `name` (string)
- `is_deleted` (boolean, default false)
- `deleted_at` (timestamptz, nullable)
- `created_at` (timestamptz, default now)

Single-level for MVP per PRD §5 (no `parent_id` needed yet — two-level income categories are a v3 item per PRD, schema-ready via self-referencing `parent_id` when actually needed, not added now to avoid an unused column).

### expense_categories
- `id` (UUID, PK)
- `family_budget_id` (UUID, FK → family_budgets.id, indexed, not null)
- `name` (string)
- `parent_id` (UUID, FK → expense_categories.id, nullable, self-referencing) — null = top-level category, non-null = subcategory. Two-level hierarchy per PRD §5.
- `is_deleted` (boolean, default false)
- `deleted_at` (timestamptz, nullable)
- `created_at` (timestamptz, default now)

### transactions
- `id` (UUID, PK)
- `family_budget_id` (UUID, FK → family_budgets.id, indexed, not null)
- `type` (string: `"income"` | `"expense"` | `"transfer"`)
- `wallet_id` (UUID, FK → wallets.id, not null) — for income/expense. For transfer, see `to_wallet_id` below.
- `to_wallet_id` (UUID, FK → wallets.id, nullable) — only set when `type = "transfer"`; `wallet_id` acts as "from wallet" in that case.
- `amount` (integer, not null) — integer only, no cents, per PRD §6
- `to_amount` (integer, nullable) — only set when `type = "transfer"` and currencies differ (result of rate conversion, PRD §4.4); null when same-currency transfer or non-transfer.
- `rate` (numeric, nullable) — only set when `type = "transfer"` and currencies differ; PRD §4.4 convention: always "UZS per 1 USD" regardless of direction.
- `income_category_id` (UUID, FK → income_categories.id, nullable) — set only when `type = "income"`
- `expense_category_id` (UUID, FK → expense_categories.id, nullable) — set only when `type = "expense"`
- `comment` (text, nullable)
- `created_by_user_id` (UUID, FK → users.id, not null) — PRD §8, needed for per-member analytics later + edit/delete permission checks
- `transaction_date` (timestamptz, not null) — user-entered date/time (PRD §4.2–4.4 datetime picker), distinct from `created_at`
- `is_deleted` (boolean, default false) — covers Owner/Member transaction deletion per PRD §3 role rules
- `deleted_at` (timestamptz, nullable)
- `created_at` (timestamptz, default now)

Note: using one `transactions` table with a `type` discriminator and nullable category FKs (rather than 3 separate tables) matches PRD §5's explicit decision to split `income_categories`/`expense_categories` as separate entities, while keeping a single transactions table for simpler History/Analytics queries (PRD §4.5, §4.6 both query across all types together). If this proves awkward in Task 05/06, it can be revisited — not a hard PRD requirement, just the simpler default for Task 02.

## Indexes

- `users.telegram_id` — unique index (auth lookups every request)
- `wallets.family_budget_id`, `income_categories.family_budget_id`, `expense_categories.family_budget_id`, `transactions.family_budget_id` — all indexed (every query is scoped by family budget, PRD §10 NFR)
- `transactions.transaction_date` — indexed (History filters by date range, PRD §4.5)
- `transactions.created_by_user_id` — indexed (permission checks + future per-member analytics)
- Optional (implementer's discretion, not required for MVP): partial indexes filtered `WHERE is_deleted = false` on the family_budget_id indexes above, since nearly every query will filter out deleted rows anyway. Not required — a plain index plus an explicit `WHERE is_deleted = false` clause in queries is sufficient for MVP data volumes.

## Default seed data (NOT created by this migration — for Task 03 reference only)

Hardcoded in onboarding code (Task 03), not a database template table. Documenting here so Task 03 references the exact same list without re-asking:

**Default income categories:** Зарплата, Подработка, Подарки, Прочее

**Default expense categories (category → subcategories):**
- Еда → Продукты, Обед, Вода и напитки, Кафе
- Развлечения → Playstation, Кино, Подписки
- Транспорт → Такси, Топливо
- Дом → Аренда, Коммуналка
- Прочее → Другое

**Default wallets (updated 2026-07-21 — see Changelog):** Карта сум
(UZS), Наличный сум (UZS), Карта USD (USD), Наличный USD (USD)

This list is a one-time starter set copied into a new Family Budget's real tables on first `/start` — after copying, they are ordinary editable/soft-deletable records, no special "template" status.

## Acceptance criteria

- [ ] Alembic migration creates all 6 tables with correct columns, types, FKs, and indexes listed above
- [ ] All primary keys are UUID, generated at the application layer (`uuid.uuid4()` default in SQLAlchemy models)
- [ ] All 6 tables include `is_deleted` (default false) and `deleted_at` (nullable)
- [ ] `users.family_budget_id` and `users.role` are **NOT NULL** (confirmed 2026-07-11 — no transitional state exists, both are set together when the row is created in Task 03's `/start` handler)
- [ ] Migration runs clean on empty DB (`alembic upgrade head`)
- [ ] Migration is reversible (`alembic downgrade -1` drops everything cleanly)
- [ ] All FKs enforce referential integrity (e.g. inserting a transaction with a non-existent `wallet_id` fails)
- [ ] SQLAlchemy models exist for all 6 tables, async-compatible (per existing `SQLAlchemy 2.0.51 async` setup), with UUID PK columns

## Verification (manual, before moving to task 03)

1. `alembic upgrade head` on empty DB — confirm no errors.
2. Inspect schema via `psql` (`\d+ <table>` for each of the 6 tables) — confirm columns/types/FKs match this spec, PKs are `uuid` type.
3. `alembic downgrade -1` — confirm all 6 tables drop cleanly, `alembic upgrade head` again to restore.
4. Manually insert one row per table via `psql` or a quick script, respecting FK order (family_budgets → users → wallets/categories → transactions) — confirm no constraint errors, confirm inserted `id` values are real UUIDs (not sequential integers).
5. Manually set `is_deleted = true` on one test row (any table) — confirm the row still exists in the table (not removed), and that `deleted_at` can be set alongside it.

## Changelog

- **2026-07-21**: Default wallet seed template updated from 3 wallets
  (Основной, Карта Uzcard, USD кошелёк) to 4 wallets (Карта сум,
  Наличный сум, Карта USD, Наличный USD). Implemented in Task 03
  `SEED_WALLETS`; income/expense category seed data unchanged.
- **2026-07-11**: Task 02 implemented and manually verified. All 5 acceptance criteria + 5 verification steps passed.
- **2026-07-11 (bug found during manual verification)**: `expense_categories.parent_id` was created as `NOT NULL` by the implementing agent, contradicting this spec (which requires it nullable — top-level categories must have `parent_id = NULL`). Fixed via a separate follow-up migration `96192ca13fd1_expense_categories_parent_id_nullable.py` (the original migration `a1b2c3d4e5f6` was left untouched since it was already applied). Confirmed via `psql`: `parent_id` is now nullable; downgrade/upgrade cycle on the fix migration verified clean; inserting a top-level category with `parent_id = NULL` succeeds. Test/verification rows were removed from all 6 tables afterward — database is empty and ready for Task 03.