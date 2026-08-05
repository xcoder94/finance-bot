# Phase 16 Task A — Protected Categories Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze seed parents «Еда», «Дом», «Здоровье» (`food`/`home`/`health`) so new budgets cannot delete or rename them; exclude protected parents from the 8-parent create limit; hide delete/rename controls in the UI.

**Architecture:** Add `expense_categories.is_protected` (boolean, NOT NULL, default false) via Alembic with no backfill. Set `True` only in `copy_seed_categories_only` for the three parent `translation_key`s when seeding new budgets. API rejects PATCH/DELETE on protected rows; create-limit count excludes `is_protected=True`. Frontend gates swipe-delete and parent danger-delete on `is_protected`.

**Tech Stack:** Python/FastAPI/SQLAlchemy/Alembic/pytest; React/TypeScript/vitest.

## Global Constraints

- Worker model: `composer-2.5` only (never `composer-2.5-fast`).
- Verbatim user-facing strings; forbidden words: ошибка, сессия, сервер, токен, запрос.
- No dead controls — hide delete/rename for protected categories (not disabled).
- Do not edit `AGENTS.md`, `docs/PRD.md`, `docs/design/**`, `docs/tasks/*.md`, `docs/context/**`.
- Never `git add` or commit anything under `docs/context/`.
- Git allowed only on branch `mvp2/phase-16-cascade-demo-protected-support`: add/commit/status/log/diff. No push/checkout/reset/etc.
- Limit message stays exactly: `Больше 8 категорий расходов создать нельзя. Удалите ненужную — место освободится.`
- Forward-only protection: migration must NOT UPDATE any existing rows.
- Protected list: parents only with keys `food`, `home`, `health`. Subcategories remain fully editable.
- Pytest: `cd backend && ./venv/bin/pytest -q` (needs Postgres). Frontend: `cd frontend && npx vitest run --reporter=dot`.
- Do not touch `ru.json`/`uz.json`.

---

### Task 1: Migration + model `is_protected`

**Files:**
- Create: `backend/alembic/versions/s9b0c1d2e3f4_expense_category_is_protected.py` (revision id may be adjusted to match repo style; `down_revision = "r8a9b0c1d2e3"`)
- Modify: `backend/app/models/expense_category.py`
- Test: `backend/tests/test_phase16_protected_categories.py` (new)

**Interfaces:**
- Produces: `ExpenseCategory.is_protected: Mapped[bool]` default `False`, column NOT NULL with server_default false.

- [ ] **Step 1: Write failing schema/model test**

```python
# backend/tests/test_phase16_protected_categories.py
import pytest
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine
from app.models.expense_category import ExpenseCategory


async def _reset_engine() -> None:
    await engine.dispose()


@pytest.mark.anyio
async def test_is_protected_column_exists_not_null_default_false():
    await _reset_engine()
    async with engine.connect() as conn:
        def check(sync_conn):
            cols = {c["name"]: c for c in inspect(sync_conn).get_columns("expense_categories")}
            assert "is_protected" in cols
            assert cols["is_protected"]["nullable"] is False
        await conn.run_sync(check)


@pytest.mark.anyio
async def test_new_expense_category_defaults_is_protected_false(session: AsyncSession, family_budget):
    cat = ExpenseCategory(
        family_budget_id=family_budget.id,
        name="Тест",
        parent_id=None,
        color_index=1,
    )
    session.add(cat)
    await session.commit()
    await session.refresh(cat)
    assert cat.is_protected is False
```

Adapt fixtures to match existing test helpers in `tests/` (reuse whatever family/session fixtures `test_phase6_settings.py` uses — do not invent a new fixture stack).

- [ ] **Step 2: Run test — expect FAIL** (column missing / attribute missing)

Run: `./venv/bin/pytest tests/test_phase16_protected_categories.py -q`

- [ ] **Step 3: Add migration + model field**

Migration upgrade:

```python
def upgrade() -> None:
    op.add_column(
        "expense_categories",
        sa.Column(
            "is_protected",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("expense_categories", "is_protected")
```

Model:

```python
is_protected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
```

No UPDATE / backfill of existing rows.

- [ ] **Step 4: Apply migration in test env if tests use live DB**

Run alembic upgrade head if schema tests hit live Postgres (same pattern as other schema tests).

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/s9b0c1d2e3f4_expense_category_is_protected.py \
  backend/app/models/expense_category.py \
  backend/tests/test_phase16_protected_categories.py \
  docs/superpowers/plans/2026-08-05-phase16-task-a-protected-categories.md
git commit -m "$(cat <<'EOF'
feat(categories): add is_protected column for expense categories

EOF
)"
```

(Only commit the plan file once, with the first Task A commit if not already committed.)

---

### Task 2: Seed sets protection; API rejects delete/rename; limit excludes protected

**Files:**
- Modify: `backend/app/services/budget_seed.py` (`copy_seed_categories_only`)
- Modify: `backend/app/schemas/wallets_categories.py` (`ExpenseCategoryResponse` add `is_protected: bool`)
- Modify: `backend/app/api/v1/categories.py` (list/create response, PATCH/DELETE guards, parent count filter)
- Modify: `backend/tests/test_phase16_protected_categories.py`
- Possibly update: `backend/tests/test_phase6_settings.py` if limit tests assume all parents count toward 8 after full seed — adjust expectations only if they become incorrect.

**Interfaces:**
- Consumes: `ExpenseCategory.is_protected`
- Produces: seed parents with `translation_key in {"food","home","health"}` get `is_protected=True`; API exposes the flag; DELETE/PATCH of protected → 403 or 409 (pick one consistent with existing style — prefer 409 with a short non-forbidden-word detail, or plain 403 with no body inventing PRD text; if no PRD string exists, use HTTP 403 without user-facing invented copy, or reuse a generic pattern already in the codebase).

**Protected keys constant** (in `budget_seed.py` or a small helper):

```python
PROTECTED_EXPENSE_PARENT_KEYS = frozenset({"food", "home", "health"})
```

In `copy_seed_categories_only`, when constructing parent:

```python
parent = ExpenseCategory(
    ...
    translation_key=parent_key,
    is_protected=parent_key in PROTECTED_EXPENSE_PARENT_KEYS,
    ...
)
```

Limit check change:

```python
.where(
    ExpenseCategory.family_budget_id == user.family_budget_id,
    ExpenseCategory.is_deleted.is_(False),
    ExpenseCategory.parent_id.is_(None),
    ExpenseCategory.is_protected.is_(False),
)
```

PATCH/DELETE after load:

```python
if category.is_protected:
    raise HTTPException(status_code=403)
```

Include `is_protected=category.is_protected` in every `ExpenseCategoryResponse` construction in this file.

- [ ] **Step 1: Write failing behavioral tests** covering:
  1. After `copy_seed_categories_only` / `copy_seed_data`, parents food/home/health have `is_protected=True`; transport/etc. False; all subs False.
  2. DELETE protected parent → 403; PATCH rename protected → 403.
  3. DELETE/PATCH unprotected parent and any subcategory (including under food) still succeed.
  4. Limit: with seeded budget (3 protected + 4 unprotected), create parents until 8 non-protected; 9th non-protected → 409 with exact `LIMIT_EXPENSE_PARENTS` text. Protected rows must not consume the 8.
  5. Manually inserted parent with default `is_protected=False` (simulating pre-migration family «Еда») remains deletable/renamable even if name is «Еда» / key `food`.

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Implement seed + schema + API**

- [ ] **Step 4: Run focused + full backend suite**

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(categories): protect food/home/health and exclude from parent limit

EOF
)"
```

---

### Task 3: Frontend expose `is_protected` and hide controls

**Files:**
- Modify: `frontend/src/api/categories.ts` — add `is_protected: boolean` to `ExpenseCategoryResponse`
- Modify: `frontend/src/pages/settings/ExpenseCategoriesSettingsPage.tsx` — `swipeDeleteEnabled={isOwner && !group.parent.is_protected}`; count for `atLimit` must count only non-protected parents
- Modify: `frontend/src/pages/settings/ExpenseSubcategoriesSettingsPage.tsx` — hide parent `dangerLabel`/`onDanger` when `parent.is_protected`; keep subcategory delete/rename as today
- Modify: `frontend/src/utils/settingsSubtitles.ts` — add `countNonProtectedExpenseParents` (or extend count helper) used for limit UI
- Test: add/adjust unit tests for the new count helper in `settingsSubtitles.test.ts`; optional small test if page tests exist (they don't — helper test is enough)

**Limit UI:** `atLimit` / `limitMessage` must use non-protected parent count only, matching backend.

```typescript
export function countNonProtectedExpenseParents(
  categories: Array<{ parent_id: string | null; is_protected?: boolean }>,
): number {
  return categories.filter((c) => c.parent_id === null && !c.is_protected).length
}
```

- [ ] **Step 1: Write failing helper test**

- [ ] **Step 2: Implement frontend changes**

- [ ] **Step 3: Run `npx vitest run --reporter=dot`**

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(frontend): hide delete for protected expense parents

EOF
)"
```

---

### Task 4: Final Task A verification

- [ ] **Step 1:** `./venv/bin/pytest -q` — counts must be ≥ baseline (or equal if only new tests added to pass count).
- [ ] **Step 2:** `npx vitest run --reporter=dot`
- [ ] **Step 3:** Confirm no `docs/context/` files staged; `git status` clean except pre-existing dirty docs/AGENTS if left unstaged.
- [ ] **Step 4:** Write report path `.superpowers/sdd/task-a-report.md` with acceptance checklist and test numbers.

**Note on parent rename UI:** expense parents currently have no rename control in the UI (only API PATCH). Hiding rename is N/A for parents in UI; API still rejects PATCH. Subcategory rename stays available under protected parents.
