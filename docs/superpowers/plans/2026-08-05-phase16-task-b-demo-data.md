# Phase 16 Task B — Demo Data + Clear-Demo Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Seed realistic previous-month demo transactions (`is_demo=True`) on every brand-new budget, and let the owner clear them with one Settings control «Очистка демо данных» that disappears when none remain.

**Architecture:** Add `transactions.is_demo` boolean NOT NULL default false (no backfill). New `seed_demo_operations(session, family_budget_id, created_by_user_id)` in `budget_seed.py` inserts the exact expense/income breakdown into the previous calendar month on shared `card_uzs` / `card_usd` wallets. Call it after `/start` `copy_seed_data` and after membership detach creates a new solo budget. Clear endpoint deletes only `is_demo=True` rows for the family; Settings shows the button only for owners when any demo rows exist.

**Tech Stack:** Python/FastAPI/SQLAlchemy/Alembic/pytest; React/TypeScript/vitest.

## Global Constraints

- Worker model: `composer-2.5` only.
- Do not edit AGENTS.md, docs/PRD.md, docs/design/**, docs/tasks/**, docs/context/**. Never commit docs/context/.
- Git: add/commit/status/log/diff only on current branch. No push/checkout/reset.
- Do not touch `ru.json`/`uz.json` — hardcode button text exactly `Очистка демо данных` in the component.
- Forbidden words in user-facing text: ошибка, сессия, сервер, токен, запрос.
- No dead controls: button must not render when no demo rows / for non-owners.
- No confirmation dialog on clear — tap deletes immediately.
- Amounts are integer minor units as elsewhere in this codebase (UZS and USD stored as integers — match existing transaction amount convention; check how USD $150 is stored in tests before writing seed amounts).
- The product model is `Transaction` in `backend/app/models/transaction.py` (there is no `operation.py`). Column name still `is_demo` per spec.
- Baseline after Task A: pytest 422, vitest 206 — must not shrink.
- Alembic `down_revision` = `s9b0c1d2e3f4`.

## Correction to prompt §7.1.3 (report this)

- Production `copy_seed_data` call sites: **only** `backend/bot/onboarding.py` (~line 289).
- Auto-budget for removed/left members is `backend/app/services/membership_lifecycle.py` which calls `copy_seed_categories_only` + conditional `copy_seed_wallets_only` — **not** `copy_seed_data`.
- Per architect default: hook demo seeding into **both** onboarding after `copy_seed_data` **and** membership detach after the new budget’s wallets are ready.

For membership detach when the member brings personal wallets (shared seed wallets not copied): before seeding demo, ensure shared `card_uzs` / `card_usd` exist — if missing, call `copy_seed_wallets_only` then seed. If that would double-count wallets when shared already exist, only call when lookups by `translation_key` miss. Flag this clearly in the report.

---

### Task 1: Migration + model `is_demo`

**Files:**
- Create: `backend/alembic/versions/t0c1d2e3f4a5_transaction_is_demo.py`
- Modify: `backend/app/models/transaction.py`
- Test: `backend/tests/test_phase16_demo_data.py` (new)

```python
# migration
def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default="false"),
    )

def downgrade() -> None:
    op.drop_column("transactions", "is_demo")
```

```python
# model
is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
```

- [ ] Write failing column/default tests (same pattern as Task A schema test).
- [ ] Implement migration + model; `alembic upgrade head`.
- [ ] Commit: `feat(transactions): add is_demo column`

---

### Task 2: `seed_demo_operations` + hook call sites

**Files:**
- Modify: `backend/app/services/budget_seed.py` — add `seed_demo_operations`
- Modify: `backend/bot/onboarding.py` — after `copy_seed_data`, call seed with the new owner’s user id
- Modify: `backend/app/services/membership_lifecycle.py` — after wallet setup on new solo budget, ensure shared card wallets, then seed with `departing_user.id`
- Test: expand `test_phase16_demo_data.py`

**Function signature:**

```python
async def seed_demo_operations(
    session: AsyncSession,
    family_budget_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
) -> None:
    ...
```

**Content (previous calendar month only):**

Resolve categories by `translation_key` among active rows for the family. Resolve wallets by `translation_key` `card_uzs` (UZS) and `card_usd` (USD).

Expenses (split into N ops totaling amount; short realistic comments, no word «demo»):

| key | total | N | currency |
|---|---|---|---|
| groceries | 2_200_000 | 4 | UZS |
| cafes_restaurants | 600_000 | 2 | UZS |
| utilities | 900_000 | 1 | UZS |
| telecom_internet | 250_000 | 1 | UZS |
| taxi | 700_000 | 3 | UZS |
| fuel | 900_000 | 2 | UZS |
| pharmacy | 450_000 | 1 | UZS |
| clothing | 1_000_000 | 1 | UZS |
| entertainment | 150 | 2 | USD |
| repairs_furnishing | 350 | 1 | USD |

Income:

| key | total | N | notes |
|---|---|---|---|
| salary | 8_000_000 UZS | 1 | early in month |
| side_job | 1_000_000 UZS | 1 | |
| family_transfers | 600 USD | 1 | |

Net: UZS +2_000_000, USD +100.

Each row: `type` income/expense, `is_demo=True`, `transaction_date` timezone-aware in previous month, `created_by_user_id` set, `comment` short realistic (e.g. «продукты», «такси», «зарплата»).

Spread UZS dates across the month. Exact days are implementer choice.

**Onboarding hook** (after `await copy_seed_data(...)`, user already flushed):

```python
await seed_demo_operations(session, budget.id, user.id)
```

**Membership hook** (end of detach-new-budget function, before return): ensure card wallets, then `await seed_demo_operations(session, new_budget.id, departing_user.id)`.

- [ ] Failing tests: after onboarding-style seed, previous month has expected totals/counts/`is_demo`; current month empty of demo; membership detach path also gets demo when no personal wallets (and with personal wallets after ensuring shared cards).
- [ ] Implement.
- [ ] Commit: `feat(seed): seed previous-month demo transactions on new budgets`

---

### Task 3: Clear-demo API + Settings button

**Files:**
- Backend: add owner-only endpoints, e.g. in `backend/app/api/v1/me.py` or a small new router registered like others:
  - `GET /demo-data` or include `has_demo_data: bool` on an existing me/settings payload — prefer minimal: `GET /api/v1/demo-data/status` → `{ "has_demo_data": bool }` and `DELETE /api/v1/demo-data` deletes all family transactions where `is_demo.is_(True)` (hard delete or soft-delete — **match how other deletes work**; if transactions use soft-delete elsewhere for user deletes, use the same for clear so analytics stay consistent; if clear should truly wipe demo, hard delete is OK for rows that never mattered — prefer **same soft_delete pattern as transaction delete** if one exists, else hard delete of `is_demo` rows. Check `transactions` delete service and follow it.)
- Frontend: `SettingsPage.tsx` — owner-only button labeled exactly `Очистка демо данных` (hardcoded, not i18n). Visible only when status says demo exists. On tap: call DELETE, refresh status, button disappears. No confirm dialog.
- Types/API client: `frontend/src/api/demoData.ts` (new, small).
- Tests: backend API tests for owner clear, member 403, non-demo rows untouched; frontend unit test optional for visibility helper if extracted.

**Visibility logic:**
```
showClearDemo = user.role === 'owner' && hasDemoData === true
```
Do not render the control at all otherwise.

- [ ] Implement + tests.
- [ ] Commit: `feat(settings): owner clear-demo-data control`

---

### Task 4: Verify Task B

- [ ] `./venv/bin/pytest -q` ≥ 422 (+ new tests)
- [ ] `npx vitest run --reporter=dot` ≥ 206
- [ ] Report: `/home/xon/Documents/finance-bot/.superpowers/sdd/task-b-report.md` with hook-site confirmation and acceptance checklist.
