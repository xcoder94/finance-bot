# Phase 10 — Editing others' operations and the change log

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Worker model:** `composer-2.5` only. Do not substitute.

**Goal:** Any family member can edit/delete shared-wallet operations; personal ops stay holder-only; authorship never changes; History edit sheets show an `Изменения` block with frozen text change lines after the first edit.

**Architecture:** New `transaction_change_logs` table stores fully formatted display lines (creation line once on first edit, then one row per changed field). Update services compare old vs new field display values, append log rows, never touch `created_by_user_id`. Shared-wallet modify permission opens to every active family member. GET/PATCH transaction responses include `changes: string[]` (empty when never edited). Frontend FormSheet gains a design-matched changes block between fields and primary actions.

**Tech Stack:** Python/FastAPI/Alembic/pytest; React/Vite/TypeScript/TelegramUI/Zustand/react-i18next; vitest. No new packages.

## Global Constraints

- Spec: `docs/tasks/phase-10-change-log.md` + PRD §14 (14.1, 14.2, Acceptance) + §17.7 edit-form differences only.
- Design: operation edit sheet `Изменения` block one-to-one (`docs/design/Chontak MVP2.dc.html` `editDirty` / `hasChanges`).
- Any member edits/deletes any SHARED-wallet operation. PERSONAL: holder only (visibility 404 for others).
- Authorship (`created_by_user_id`) never changes on edit.
- Operation type is not editable — no control may flip expense↔income.
- Block title exactly: `Изменения`
- Creation line exactly: `{day} {genitive month} · создал {display_name}` (middle dot U+00B7 with spaces).
- Change line exactly: `{day} {genitive month} · {editor}: {field} {old} → {new}` (arrow U+2192).
- Genitive months exactly: января · февраля · марта · апреля · мая · июня · июля · августа · сентября · октября · ноября · декабря
- Field labels lower case exactly: сумма, категория, кошелёк, дата, комментарий; transfer/exchange also откуда, куда, курс
- One line per changed field; unchanged omitted; multi-field edit → several lines sharing one date.
- Old values stored as TEXT at edit time; later wallet/category rename must not alter existing lines.
- Long values truncated with ellipsis (CSS on the line, as design).
- Block absent entirely until first edit — not empty, not placeholder.
- Deletion not logged; deleted ops unreachable in History; no revert.
- Every edit logged (own and others'; shared and personal).
- Do **not** edit `AGENTS.md`, `CLAUDE.md`, `docs/PRD.md`, `docs/design/*`, `docs/tasks/*`, `frontend/src/utils/memberConfirmCopy.ts`.
- Worker: `composer-2.5` only. Branch: `mvp2/phase-10-change-log` (already checked out).
- Git allowed: add, commit, status, log, diff. Forbidden: push, pull, fetch, stash, checkout, switch, restore, reset, revert, branch, merge, rebase, clean, cherry-pick, tag, remote.
- Baseline must still pass: backend 326 pytest; frontend 187 vitest / 35 files.
- Stop at end of Phase 10 — no Phase 11, notifications, bot chrome, voice, photo, caching.
- User-facing Russian verbatim. Forbidden words: ошибка, сессия, сервер, токен, запрос.
- Confidence below average → write «not sure», do not guess.
- Conversation/report language with customer is Russian; this plan is English (docs/).

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/services/change_log_format.py` | Genitive months, amount/date/rate text, creation/change line builders |
| `backend/app/services/change_log.py` | Diff fields, ensure creation line, append change rows, load lines |
| `backend/app/models/transaction_change_log.py` | ORM for log rows |
| `backend/alembic/versions/p6e7f8a9b0c1_transaction_change_logs.py` | Migration (revises `o5d6e7f8a9b0`) |
| `backend/app/models/__init__.py` | Export new model |
| `backend/app/schemas/transactions.py` | `changes: list[str] = []` on `TransactionResponse` |
| `backend/app/services/transactions.py` | Shared-member edit permission; call change-log recorder in updates |
| `backend/app/api/v1/transactions.py` | Include changes on GET/PATCH responses |
| `backend/tests/test_change_log_format.py` | Pure format unit tests |
| `backend/tests/test_phase10_change_log.py` | API acceptance: permissions, authorship, lines, rename freeze, absent block, delete, personal hidden |
| `backend/tests/test_transactions.py` | Flip member-on-shared 403 → 200 |
| `frontend/src/components/forms/ChangesBlock.tsx` | Design block UI |
| `frontend/src/components/forms/ChangesBlock.test.tsx` | Absent when empty; renders title + lines |
| `frontend/src/components/forms/FormSheet.tsx` | Optional `changes` slot between fields and actions |
| `frontend/src/index.css` | `.form-sheet-changes*` matching design |
| `frontend/src/api/transactions.ts` | `changes?: string[]` on `TransactionResponse` |
| `frontend/src/pages/EditExpensePage.tsx` | Pass `changes` into FormSheet |
| `frontend/src/pages/EditIncomePage.tsx` | Same |
| `frontend/src/pages/EditTransferPage.tsx` | Same |
| `frontend/src/i18n/locales/ru.json` | Key for title `Изменения` (verbatim) |

---

### Task 1: Change-log format helpers

**Files:**
- Create: `backend/app/services/change_log_format.py`
- Test: `backend/tests/test_change_log_format.py`

**Interfaces:**
- Produces:
  - `MONTH_GENITIVE: tuple[str, ...]` — 12 exact forms
  - `format_day_month(d: date) -> str` — e.g. `"1 августа"`
  - `format_amount_text(amount: int) -> str` — thousands with spaces, no currency (reuse logic from `bot.quick_entry.cards.format_number`)
  - `format_transaction_date_text(dt: datetime) -> str` — `DD.MM.YYYY` in `Asia/Tashkent`
  - `format_rate_text(rate: Decimal) -> str` — whole numbers without decimals; otherwise normalize trailing zeros
  - `creation_line(*, created_on: date, creator_name: str) -> str`
  - `change_line(*, edited_on: date, editor_name: str, field_label: str, old_value: str, new_value: str) -> str`
  - Field label constants: `FIELD_AMOUNT = "сумма"`, `FIELD_CATEGORY = "категория"`, `FIELD_WALLET = "кошелёк"`, `FIELD_DATE = "дата"`, `FIELD_COMMENT = "комментарий"`, `FIELD_FROM = "откуда"`, `FIELD_TO = "куда"`, `FIELD_RATE = "курс"`
- Consumes: nothing.

- [ ] **Step 1: Write failing tests**

```python
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.services.change_log_format import (
    FIELD_AMOUNT,
    MONTH_GENITIVE,
    change_line,
    creation_line,
    format_amount_text,
    format_day_month,
    format_rate_text,
    format_transaction_date_text,
)

TASHKENT = ZoneInfo("Asia/Tashkent")


def test_month_genitive_exact():
    assert MONTH_GENITIVE == (
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря",
    )


def test_creation_and_change_lines_match_prd():
    assert creation_line(created_on=date(2026, 8, 1), creator_name="Рустам") == (
        "1 августа · создал Рустам"
    )
    assert change_line(
        edited_on=date(2026, 8, 2),
        editor_name="Дилноза",
        field_label=FIELD_AMOUNT,
        old_value="20 000",
        new_value="200 000",
    ) == "2 августа · Дилноза: сумма 20 000 → 200 000"
    assert "→" in change_line(
        edited_on=date(2026, 8, 2),
        editor_name="Дилноза",
        field_label="категория",
        old_value="Продукты",
        new_value="Такси",
    )
    assert " · " in creation_line(created_on=date(2026, 1, 1), creator_name="A")


def test_amount_date_rate_helpers():
    assert format_amount_text(20_000) == "20 000"
    assert format_amount_text(200_000) == "200 000"
    assert format_day_month(date(2026, 8, 1)) == "1 августа"
    dt = datetime(2026, 8, 29, 10, 0, tzinfo=TASHKENT)
    assert format_transaction_date_text(dt) == "29.08.2026"
    assert format_rate_text(Decimal("12800")) == "12800"
    assert format_rate_text(Decimal("12.50")) == "12.5"
```

- [ ] **Step 2: Run tests — expect FAIL** (module missing)

Run: `cd backend && ./venv/bin/pytest tests/test_change_log_format.py -q`

- [ ] **Step 3: Implement** `change_log_format.py` with the helpers above. Separators: middle dot `·` (U+00B7), arrow `→` (U+2192). Do not import from bot package if that creates circular deps — copy `format_number` logic into this module (or a tiny shared private function in the same file).

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/change_log_format.py backend/tests/test_change_log_format.py
git commit -m "$(cat <<'EOF'
feat(change-log): add PRD line format helpers

EOF
)"
```

---

### Task 2: Model + Alembic migration

**Files:**
- Create: `backend/app/models/transaction_change_log.py`
- Create: `backend/alembic/versions/p6e7f8a9b0c1_transaction_change_logs.py`
- Modify: `backend/app/models/__init__.py`

**Interfaces:**
- Produces model `TransactionChangeLog`:
  - `id: UUID` PK
  - `transaction_id: UUID` FK → `transactions.id`, indexed, not null
  - `line_text: Text` not null — fully formatted display line
  - `created_at: DateTime(timezone=True)` server default now (via `TimestampMixin` or explicit column)
  - Order of lines for a transaction: `created_at` asc, then `id` asc
- Migration revision: `p6e7f8a9b0c1`, down_revision: `o5d6e7f8a9b0`

- [ ] **Step 1: Write a small migration smoke test** in `backend/tests/test_phase10_change_log.py` that imports the model and asserts `__tablename__ == "transaction_change_logs"`.

```python
from app.models.transaction_change_log import TransactionChangeLog

def test_change_log_model_tablename():
    assert TransactionChangeLog.__tablename__ == "transaction_change_logs"
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement model + migration + export in `__init__.py`**

Model sketch:

```python
class TransactionChangeLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "transaction_change_logs"

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False, index=True
    )
    line_text: Mapped[str] = mapped_column(Text, nullable=False)
```

Migration: `create_table` with id, transaction_id, line_text, created_at, updated_at if TimestampMixin has both — match `ownership_transfers` / TimestampMixin columns exactly.

- [ ] **Step 4: Run test — expect PASS**. Also confirm alembic head chain: `./venv/bin/alembic heads` shows `p6e7f8a9b0c1`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/transaction_change_log.py backend/app/models/__init__.py backend/alembic/versions/p6e7f8a9b0c1_transaction_change_logs.py backend/tests/test_phase10_change_log.py
git commit -m "$(cat <<'EOF'
feat(change-log): add transaction_change_logs table

EOF
)"
```

---

### Task 3: Permission — any member may edit shared ops

**Files:**
- Modify: `backend/app/services/transactions.py` (`require_transaction_modify_permission`)
- Modify: `backend/tests/test_transactions.py` (`TestEditDeletePermissions.test_member_forbidden_on_others_transactions_allowed_on_own`)

**Interfaces:**
- After change, for SHARED wallets (not personal): any visible member may PATCH/DELETE — do **not** call `require_modify_permission`.
- For PERSONAL: keep holder-only checks (404 if not holder).
- `require_modify_permission` may remain for clarity but must not gate shared edits.

- [ ] **Step 1: Update the existing test** so member PATCH/DELETE on owner's **shared** txn expects **200**, and keep a personal-wallet case expecting 404 for non-holder (add if missing — see Phase 7 tests; if already covered in `test_phase7_personal_wallets.py`, only flip the shared 403→200 assertions).

Change in `test_transactions.py`:

```python
# was 403 / 403 — Phase 10: any member may edit shared
assert (await client.patch(...owner_txn...)).status_code == 200
assert (await client.delete(...owner_txn...)).status_code == 200
```

Rename test to `test_member_can_edit_and_delete_others_shared_transactions` (or keep name and fix body). Also assert `created_by_user_id` unchanged after member patch.

- [ ] **Step 2: Run test — expect FAIL** (still 403)

- [ ] **Step 3: Implement**

```python
def require_transaction_modify_permission(...):
    require_transaction_visible(from_wallet, to_wallet, user)
    if is_personal_wallet_transaction(from_wallet, to_wallet):
        if from_wallet.is_personal and from_wallet.owner_user_id != user.id:
            raise HTTPException(status_code=404)
        if to_wallet is not None and to_wallet.is_personal and to_wallet.owner_user_id != user.id:
            raise HTTPException(status_code=404)
        return
    # Shared: any family member who can see it may modify.
    return
```

- [ ] **Step 4: Run `test_transactions.py::TestEditDeletePermissions` + phase7 personal edit tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/transactions.py backend/tests/test_transactions.py
git commit -m "$(cat <<'EOF'
feat(transactions): allow any member to edit shared ops

EOF
)"
```

---

### Task 4: Change-log service + wire into updates + response schema

**Files:**
- Create: `backend/app/services/change_log.py`
- Modify: `backend/app/schemas/transactions.py` — add `changes: list[str] = []`
- Modify: `backend/app/services/transactions.py` — before mutating fields, record diffs; never change `created_by_user_id`
- Modify: `backend/app/api/v1/transactions.py` — attach changes on GET and PATCH
- Test: extend `backend/tests/test_phase10_change_log.py`

**Interfaces:**
- Produces:
  - `async def list_change_lines(session, transaction_id) -> list[str]`
  - `async def record_income_changes(session, transaction, body: IncomeUpdate, editor: User) -> None`
  - `async def record_expense_changes(session, transaction, body: ExpenseUpdate, editor: User) -> None`
  - `async def record_transfer_changes(session, transaction, body: TransferUpdate, editor: User) -> None`
- Behaviour:
  1. Build old/new display strings for each logged field.
  2. Skip fields where old == new.
  3. If no fields changed → do nothing (no creation line either).
  4. If transaction has zero log rows yet → insert creation line first using `transaction.created_at` date in Tashkent and creator display name (`first_name or username or "Unknown"`), then insert one row per changed field with **today** in Tashkent and editor display name.
  5. Store `line_text` only — names/values frozen.
  6. Income/expense fields order: сумма, категория, кошелёк, дата, комментарий.
  7. Transfer fields order: сумма, откуда, куда, курс (only if old or new rate is not None), дата, комментарий.
  8. Category value = category `name` column at edit time (not translation). Wallet = `name`. Comment = text or `""`. Amount via `format_amount_text`. Date via `format_transaction_date_text`. Rate via `format_rate_text`.
  9. Deletion must not write log rows.
- `transaction_to_response` / API: load lines into `changes`. Empty list when never edited.
- Call record_* **before** applying mutations (while old values still on the ORM object), then apply updates, then commit once (or record adds to session and commit with update).

- [ ] **Step 1: Write failing API tests** (core cases) in `test_phase10_change_log.py` using existing fixtures patterns from `test_transactions.py` / `test_phase7_personal_wallets.py`:

```python
async def test_member_b_edits_shared_amount_logs_creation_and_change(...):
    # A creates expense on shared wallet; B patches amount
    # GET shows created_by_user_id == A
    # changes[0] matches creation_line for A
    # changes[1] matches change_line for B / сумма

async def test_multi_field_edit_three_lines_one_date(...):
    # patch amount + category + comment → exactly 3 change lines after creation line
    # all change lines share the same day-month prefix

async def test_never_edited_changes_empty(...):
    # GET changes == []

async def test_wallet_rename_does_not_rewrite_old_log(...):
    # edit wallet A→B logging name "Наличные"; rename wallet; GET still shows old name in line

async def test_delete_not_logged_and_get_404(...):
    # delete; GET 404; no requirement to assert log rows (deletion writes nothing)

async def test_personal_op_hidden_from_other_member(...):
    # B cannot GET/PATCH A's personal txn (404)
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement** `change_log.py` and wire updates + schema + API.

- [ ] **Step 4: Run phase10 + transactions permission tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/change_log.py backend/app/schemas/transactions.py backend/app/services/transactions.py backend/app/api/v1/transactions.py backend/tests/test_phase10_change_log.py
git commit -m "$(cat <<'EOF'
feat(change-log): record frozen edit lines on transaction update

EOF
)"
```

---

### Task 5: Frontend ChangesBlock + FormSheet slot

**Files:**
- Create: `frontend/src/components/forms/ChangesBlock.tsx`
- Create: `frontend/src/components/forms/ChangesBlock.test.tsx`
- Modify: `frontend/src/components/forms/FormSheet.tsx` — add optional `changes?: ReactNode`
- Modify: `frontend/src/index.css` — styles matching design
- Modify: `frontend/src/i18n/locales/ru.json` — `"formSheet.changes": "Изменения"`
- Modify: `frontend/src/api/transactions.ts` — `changes?: string[]`

**Design (verbatim from prototype):**
- Wrapper: `background: var(--bg2); border-radius: 12px; padding: 12px 14px`
- Title: `font-weight 600; font-size 12.5px; line-height 1; color var(--tx)` text `Изменения`
- List: `display flex; flex-direction column; gap 7px; margin-top 9px`
- Line: `font-weight 400; font-size 11.5px; line-height 1.35; color var(--hint); white-space nowrap; overflow hidden; text-overflow ellipsis`

FormSheet order: header → intro → fields → **changes** → primary actions → danger.

- [ ] **Step 1: Write failing vitest**

```tsx
import { render, screen } from '@testing-library/react'
import { ChangesBlock } from './ChangesBlock'

it('renders nothing when lines empty', () => {
  const { container } = render(<ChangesBlock lines={[]} />)
  expect(container).toBeEmptyDOMElement()
})

it('renders title and lines', () => {
  render(
    <ChangesBlock
      lines={[
        '1 августа · создал Рустам',
        '2 августа · Дилноза: сумма 20 000 → 200 000',
      ]}
    />,
  )
  expect(screen.getByText('Изменения')).toBeTruthy()
  expect(screen.getByText('1 августа · создал Рустам')).toBeTruthy()
})
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement** ChangesBlock, FormSheet `changes` prop, CSS, i18n, API type.

`ChangesBlock` may hardcode the title string `Изменения` (PRD verbatim) or use `t('formSheet.changes')` with the same value — prefer i18n key with exact string.

- [ ] **Step 4: Run vitest for ChangesBlock — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/forms/ChangesBlock.tsx frontend/src/components/forms/ChangesBlock.test.tsx frontend/src/components/forms/FormSheet.tsx frontend/src/index.css frontend/src/i18n/locales/ru.json frontend/src/api/transactions.ts
git commit -m "$(cat <<'EOF'
feat(change-log): add Изменения block to form sheet

EOF
)"
```

---

### Task 6: Wire edit pages + confirm type not editable

**Files:**
- Modify: `frontend/src/pages/EditExpensePage.tsx`
- Modify: `frontend/src/pages/EditIncomePage.tsx`
- Modify: `frontend/src/pages/EditTransferPage.tsx`
- Test: extend `ChangesBlock.test.tsx` or small page test — assert FormSheet receives changes when `transaction.changes` non-empty; assert no type-switching control exists on edit pages (no income/expense toggle).

**Interfaces:**
- Pass `changes={<ChangesBlock lines={transaction.changes ?? []} />}` (or only when length > 0 — ChangesBlock already returns null for empty).
- After successful save, response may include updated `changes`; cache updated transaction.
- Do not add any control that changes `type`.

- [ ] **Step 1: Write a focused test** that Edit expense form source has no type toggle — simplest: grep-style unit test on a small exported constant, OR vitest that renders ChangesBlock via FormSheet with mock lines. Prefer testing FormSheet renders changes between fields and actions:

```tsx
render(
  <FormSheet open title="t" onClose={() => {}} changes={<ChangesBlock lines={['1 августа · создал Рустам']} />}>
    <div>field</div>
  </FormSheet>,
)
expect(screen.getByText('Изменения')).toBeTruthy()
```

- [ ] **Step 2: Implement page wiring**

- [ ] **Step 3: Run frontend tests — expect PASS**

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/EditExpensePage.tsx frontend/src/pages/EditIncomePage.tsx frontend/src/pages/EditTransferPage.tsx frontend/src/components/forms/ChangesBlock.test.tsx
git commit -m "$(cat <<'EOF'
feat(change-log): show Изменения on history edit sheets

EOF
)"
```

---

### Task 7: Full suite verification + acceptance checklist

**Files:** none new unless a gap found.

- [ ] **Step 1: Run backend** `./venv/bin/pytest -q` — must stay ≥326 and all phase10 green (expect more than 326 with new tests).

- [ ] **Step 2: Run frontend** `npx vitest run --reporter=dot` — 35+ files, all pass (baseline 187 + new).

- [ ] **Step 3: Confirm acceptance mapping**

| Spec §2 item | Covered by |
|---|---|
| 1 Member B edits shared amount | `test_member_b_edits_shared_amount_...` |
| 2 Authorship stays A | same + assert `created_by_user_id` |
| 3 Изменения creation + change | same |
| 4 Three fields → three lines | `test_multi_field_edit_...` |
| 5 Rename wallet freezes old line | `test_wallet_rename_...` |
| 6 Never edited → block absent | API `changes == []` + ChangesBlock empty |
| 7 No type control | edit pages unchanged / no type field |
| 8 Delete → cannot open; not logged | `test_delete_not_logged_...` |
| 9 Personal hidden from B | `test_personal_op_hidden_...` |

- [ ] **Step 4: If any gap, fix with a small commit. Do not start Phase 11.**

- [ ] **Step 5: Final commit only if fixes were needed.**

---

## Self-review

1. **Spec coverage:** §14.1 permissions + authorship; §14.2 block formats/fields/absence/no type/no delete log/no revert; §17.7 edit sheet differences (Удалить already exists; Изменения added). Design placement between fields and primary.
2. **Placeholders:** none — concrete paths, signatures, test code.
3. **Type consistency:** `changes: list[str]` / `string[]`; model `TransactionChangeLog.line_text`; helpers feed `change_log.py` → API → FormSheet.
4. **Open point:** empty comment display in change lines uses `""` (two spaces around arrow if both empty never happens; empty→text shows `комментарий  → text` with two spaces after label — matches `{field} {old} → {new}` with empty old). If product prefers a visible placeholder for empty comment — **not sure**; use empty string until told otherwise.
