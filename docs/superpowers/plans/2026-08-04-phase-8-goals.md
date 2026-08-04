# Phase 8 — Goals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Worker model:** `composer-2.5` only. Do not substitute.

**Goal:** Owner attaches a savings goal to a shared wallet; family sees progress on the Цели tab; crossing the target fans out an achievement Telegram message; owner closes the goal without moving money.

**Architecture:** A `goals` table holds active and closed goals (`wallet_id` FK; partial unique index enforces at most one active goal per wallet). Progress is always live `wallet_balance ÷ target` for active goals; closed goals store frozen balance/target at close. After any transaction write that changes a shared wallet balance, `check_goal_achievement` compares balance to target and the goal’s `crossed` flag, sending §12.3 messages only on a rising edge. Frontend replaces the Goals stub with design-matching tabs, cards, form, and owner-only controls; settings wallet rows get a goal mark; quick-entry stays unchanged.

**Tech Stack:** Python/FastAPI/Aiogram/Alembic/pytest; React/Vite/TypeScript/TelegramUI/Zustand/react-i18next; vitest. No new packages.

## Global Constraints

- Spec: `docs/tasks/phase-08-goals.md` + PRD §3, §12 (all), §16.3, §17.1, §17.2 (§12.5 xref). Shared-wallet transfer mechanism from §11 only — no new “goal contribution” transaction type.
- Design: Goals list / empty / form / achievement card states one-to-one (`docs/design/Chontak MVP2.dc.html`). Appearance wins for layout/wording on controls; PRD wins for behaviour.
- Goal = optional property of a **shared** wallet; max one **active** per wallet; no personal goals; create form lists shared wallets only.
- Only owner sees create controls and close button — members: absent, not disabled.
- Name blank → wallet name. Currency = wallet currency; not a selectable field.
- Progress = balance ÷ target × 100, display capped at 100%. Under target (design wording): `Осталось {money}`. Over target (exact): `Накоплено на {sum} {currency} больше`. At exact 100%: neither remaining nor excess line.
- Achievement text (exact, every member):
  ```
  🎯 Цель «{name}» достигнута
  Накоплено {sum} {currency} из {target}
  ```
  Inline button `[Закрыть цель]` owner only. No `Оставить` anywhere.
- Crossing: re-send only after balance drops below target then crosses again. Persist `crossed` boolean on the goal; do not re-send while continuously ≥ target.
- Close: owner only; irreversible; no money movement; card → `Достигнутые`; freeze figures; hide percentage; wallet immediately free for a new goal.
- Wallet with active goal: fully usable in quick entry / default wallet; marked as having a goal **only in settings** (subtitle append ` · цель`); never show progress on quick-entry cards.
- Deadline in the past = label only; date remains editable.
- §16.4 switches / weekly digest goal lines = Phase 11 — do not build.
- Do **not** edit `AGENTS.md`, `CLAUDE.md`, `docs/PRD.md`, `docs/design/*`, `docs/tasks/*`.
- Worker: `composer-2.5` only. Branch: `mvp2/phase-8-goals` (already checked out).
- Git allowed: add, commit, status, log, diff. Forbidden: push, pull, fetch, stash, checkout, switch, restore, reset, revert, branch, merge, rebase, clean, cherry-pick, tag, remote.
- Commit after each task. TDD. Stop at end of Phase 8 — no Phase 9, members lifecycle, change log, notification switches.
- User-facing Russian verbatim from PRD/design. Forbidden words: ошибка, сессия, сервер, токен, запрос.
- Money on Goals UI and bot achievement: thin-space/` ` grouped digits + `сум` / `$` (same as bot `format_amount` / design `money()` for UZS goals — use `сум`, not `UZS`).

## File map

| File | Responsibility |
|------|----------------|
| `backend/alembic/versions/n4c5d6e7f8a9_goals.py` | Create `goals` table + partial unique index |
| `backend/app/models/goal.py` | Goal ORM |
| `backend/app/models/__init__.py` | Export Goal |
| `backend/app/schemas/goals.py` | Request/response schemas |
| `backend/app/services/goals.py` | CRUD, progress, close, crossing check |
| `backend/app/services/goal_notify.py` | Format + fan-out achievement messages |
| `backend/app/api/v1/goals.py` | REST endpoints |
| `backend/app/main.py` | Register goals router |
| `backend/app/api/v1/wallets.py` + schemas | `has_active_goal` on WalletResponse |
| `backend/app/services/transactions.py` | Call achievement check after writes |
| `backend/bot/quick_entry/handlers.py` | Call achievement check after quick-entry writes |
| `backend/bot/goals.py` | Close-goal callback handler + router |
| `backend/bot/main.py` | Include goals router |
| `backend/tests/test_phase8_goals.py` | Backend acceptance tests |
| `frontend/src/api/goals.ts` | Goals API client |
| `frontend/src/api/wallets.ts` | `has_active_goal` on WalletResponse |
| `frontend/src/pages/GoalsPage.tsx` | Tabs, list, empty, cards |
| `frontend/src/components/goals/*` | GoalCard, GoalFormSheet, helpers |
| `frontend/src/pages/settings/WalletsSettingsPage.tsx` | Goal mark in subtitle |
| `frontend/src/i18n/locales/ru.json` | Goals strings |
| `frontend/src/*.css` | Goals styles matching design |
| Vitest files | Progress copy, owner visibility, settings mark |

---

### Task 1: Goals model + migration

**Files:**
- Create: `backend/app/models/goal.py`
- Create: `backend/alembic/versions/n4c5d6e7f8a9_goals.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_phase8_goals.py` (migration/model smoke via create)

**Interfaces:**
- Produces model `Goal` with fields:
  - `id: UUID` PK
  - `family_budget_id: UUID` FK → family_budgets, indexed
  - `wallet_id: UUID` FK → wallets, indexed (kept after close for history; does not block new active goals)
  - `name: str`
  - `target_amount: int` (>0)
  - `currency: str` (`UZS`|`USD`) — copied from wallet at create
  - `deadline: date | None`
  - `status: str` — `"active"` | `"closed"`
  - `crossed: bool` — last-known ≥-target state for rising-edge notify; default False
  - `frozen_balance: int | None` — set on close
  - `closed_at: datetime | None` (timezone-aware UTC)
  - soft-delete mixin **not** used — closed goals stay as `status=closed`
  - TimestampMixin (`created_at`, `updated_at`)
- Partial unique index: one row with `status='active'` per `wallet_id`
- Consumes: existing Wallet, FamilyBudget patterns from `app/models/wallet.py`

- [ ] **Step 1: Write failing test** in `backend/tests/test_phase8_goals.py`:

```python
@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_goal_model_roundtrip(api_client):
    client, session = api_client
    owner, budget = await create_user_with_budget(session, telegram_id=..., role="owner")
    wallet = Wallet(
        family_budget_id=budget.id,
        name="Накопления",
        currency="UZS",
        is_personal=False,
    )
    session.add(wallet)
    await session.flush()
    goal = Goal(
        family_budget_id=budget.id,
        wallet_id=wallet.id,
        name="Накопления",
        target_amount=8_000_000,
        currency="UZS",
        deadline=None,
        status="active",
        crossed=False,
    )
    session.add(goal)
    await session.commit()
    await session.refresh(goal)
    assert goal.id is not None
    assert goal.status == "active"
    assert goal.crossed is False
```

Reuse `api_client` / `create_user_with_budget` from `tests/test_wallets_categories.py` (import or duplicate the fixture pattern used in `test_phase7_personal_wallets.py`).

- [ ] **Step 2:** Run `cd backend && ./venv/bin/pytest -q tests/test_phase8_goals.py::test_goal_model_roundtrip -v` — FAIL (Goal missing).

- [ ] **Step 3: Implement** model + Alembic revision `n4c5d6e7f8a9` with `down_revision = "m3b4c5d6e7f8"`. Create table + index:

```python
op.create_index(
    "uq_goals_one_active_per_wallet",
    "goals",
    ["wallet_id"],
    unique=True,
    postgresql_where=sa.text("status = 'active'"),
)
```

Export `Goal` from `app.models`.

- [ ] **Step 4:** Same test PASS. Full `./venv/bin/pytest -q` still green (or only this file if suite needs DB — match Phase 7 practice: run full suite).

- [ ] **Step 5: Commit** `feat(goals): add goals table and model`

---

### Task 2: Goals service CRUD + REST API

**Files:**
- Create: `backend/app/schemas/goals.py`
- Create: `backend/app/services/goals.py`
- Create: `backend/app/api/v1/goals.py`
- Modify: `backend/app/main.py` — `app.include_router(goals.router)`
- Modify: `backend/tests/test_phase8_goals.py`

**Interfaces:**
- Schemas:
  - `GoalCreate`: `wallet_id: UUID`, `target_amount: int` (gt 0), `name: str | None = None`, `deadline: date | None = None`
  - `GoalUpdate`: `name: str | None = None`, `target_amount: int | None = None`, `deadline: date | None = None` (wallet immutable)
  - `GoalResponse`: `id`, `wallet_id`, `name`, `target_amount`, `currency`, `deadline`, `status`, `balance` (live or frozen), `progress_pct` (`int | None` — None when closed), `remaining_or_over` (computed string key fields — see below), `closed_at`, `can_close` (bool for current user)
- Prefer returning numeric fields + flags; let frontend format copy. API fields:
  - `balance: int`
  - `progress_pct: int | None` — `min(100, round(balance/target*100))` when active; `None` when closed
  - `excess_amount: int | None` — `balance - target` when active and balance > target; else `None`
  - `remaining_amount: int | None` — `target - balance` when active and balance < target; else `None`
  - `is_exactly_complete: bool` — active and balance == target
- Endpoints (`prefix=/api/v1`):
  - `GET /goals?status=active|closed` — CurrentUserDep; family-scoped
  - `POST /goals` — OwnerUserDep; 201
  - `PATCH /goals/{id}` — OwnerUserDep; active only
  - `POST /goals/{id}/close` — OwnerUserDep; 200
- Create rules:
  - Wallet must be active, shared (`is_personal=False`), same family
  - If wallet already has active goal → 409
  - Personal wallet → 400/422
  - Blank/None name → use `wallet.name`
  - Set `currency = wallet.currency`, `crossed = (await wallet_balance(...)) >= target_amount` without sending notify on create if already above (if balance already ≥ target at create: set `crossed=True` and **do** send achievement once — rising edge from “no goal” is a cross; implement: after create, if balance >= target, send achievement and set crossed True)
- Close rules:
  - `frozen_balance = await wallet_balance(...)`
  - `status = "closed"`, `closed_at = now(UTC)`, clear active uniqueness
  - No balance/transaction changes
- List closed: `progress_pct=None`, `balance=frozen_balance`

- [ ] **Step 1: Failing tests:**

```python
async def test_owner_creates_goal_default_name(api_client): ...
# POST without name → response.name == wallet.name

async def test_member_cannot_create_goal(api_client): ...  # 403

async def test_create_rejects_personal_wallet(api_client): ...

async def test_second_active_goal_same_wallet_409(api_client): ...

async def test_list_active_and_closed(api_client): ...

async def test_owner_closes_goal_freezes_and_frees_wallet(api_client): ...
# close → status closed, frozen_balance set, wallet balances unchanged,
# POST new goal on same wallet succeeds

async def test_member_cannot_close(api_client): ...  # 403

async def test_patch_deadline_in_past_allowed(api_client): ...
```

- [ ] **Step 2:** Focused pytest — FAIL.

- [ ] **Step 3: Implement** schemas, service, router. Register in `main.py`.

Progress helpers in `goals.py`:

```python
def progress_fields(balance: int, target: int, *, closed: bool, frozen: int | None) -> dict:
    if closed:
        return {
            "balance": frozen if frozen is not None else balance,
            "progress_pct": None,
            "excess_amount": None,
            "remaining_amount": None,
            "is_exactly_complete": False,
        }
    pct = min(100, round(balance * 100 / target)) if target > 0 else 0
    excess = balance - target if balance > target else None
    remaining = target - balance if balance < target else None
    return {
        "balance": balance,
        "progress_pct": pct,
        "excess_amount": excess,
        "remaining_amount": remaining,
        "is_exactly_complete": balance == target,
    }
```

- [ ] **Step 4:** Tests PASS; full pytest green.

- [ ] **Step 5: Commit** `feat(goals): CRUD API for shared-wallet goals`

---

### Task 3: Achievement crossing + Telegram fan-out + bot close

**Files:**
- Create: `backend/app/services/goal_notify.py`
- Create: `backend/bot/goals.py`
- Modify: `backend/bot/main.py`
- Modify: `backend/app/services/goals.py` — `check_goal_achievement(session, wallet_id, bot=None)`
- Modify: `backend/tests/test_phase8_goals.py`

**Interfaces:**
- `async def check_goal_achievement(session, wallet_id: UUID, *, bot: Bot | None = None) -> None`
  - Load active goal for wallet (if any)
  - `balance = await wallet_balance(session, wallet_id)`
  - `now_crossed = balance >= goal.target_amount`
  - If `now_crossed and not goal.crossed`: send fan-out; set `goal.crossed = True`; commit
  - If `not now_crossed and goal.crossed`: set `goal.crossed = False`; commit (no message)
  - If `now_crossed and goal.crossed`: no-op
- `format_achievement_message(name, balance, target, currency) -> str` using `format_amount` from `bot.quick_entry.cards`
- Fan-out: select all non-deleted users with `family_budget_id == goal.family_budget_id`; for each `bot.send_message(telegram_id, text, reply_markup=kb_if_owner)`
- Keyboard only for `user.role == "owner"`:

```python
InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="Закрыть цель", callback_data=f"goal:close:{goal.id}")
]])
```

- Bot router `backend/bot/goals.py`:
  - Callback `goal:close:{uuid}` → owner only closes via service; answer callback; edit message to remove button (or confirm closed). Member tapping → ignore / answer empty.
- If `bot is None`, construct `Bot(token=BOT_TOKEN)` for API-path calls (same as config). In tests, pass a mock Bot.
- Exact message (no Markdown bold required unless matching other cards — use plain text as PRD shows):

```
🎯 Цель «{name}» достигнута
Накоплено {sum} {currency} из {target}
```

where `{sum}`/`{target}` are `format_amount` without duplicating currency word twice — PRD shows `Накоплено 8 200 000 сум из 8 000 000` (currency once after first number; second number bare). Implement:

```python
def format_achievement_message(name: str, balance: int, target: int, currency: str) -> str:
    sum_s = format_amount(balance, currency)
    target_num = _format_number(target)  # reuse private or export
    return (
        f"🎯 Цель «{name}» достигнута\n"
        f"Накоплено {sum_s} из {target_num}"
    )
```

- [ ] **Step 1: Failing tests** (mock Bot.send_message):

```python
async def test_crossing_sends_to_every_member_owner_button(api_client): ...
async def test_staying_above_does_not_resend(api_client): ...
async def test_drop_below_then_cross_sends_again(api_client): ...
async def test_close_via_callback_owner(api_client): ...  # optional unit on handler
```

- [ ] **Step 2:** FAIL.

- [ ] **Step 3: Implement** notify + check + bot router; register in `bot/main.py`.

- [ ] **Step 4:** PASS + full pytest.

- [ ] **Step 5: Commit** `feat(goals): achievement fan-out and close callback`

---

### Task 4: Hook achievement check into all balance writes

**Files:**
- Modify: `backend/app/services/transactions.py` — after successful create/update/delete of income/expense/transfer, call `check_goal_achievement` for every affected shared wallet id (`wallet_id`, and `to_wallet_id` if transfer)
- Modify: `backend/bot/quick_entry/handlers.py` — after confirmed writes that create/update transactions, same hook (pass `message.bot`)
- Modify: `backend/tests/test_phase8_goals.py` — integration via POST transfer/income API

**Interfaces:**
- Consumes: `check_goal_achievement` from Task 3
- Affected wallets: only non-personal; skip personal wallets early inside check (no active goal possible)

- [ ] **Step 1: Failing test:**

```python
async def test_transfer_into_wallet_triggers_achievement(api_client):
    # create goal target 1000; transfer 1000 in via API; mock send_message called once per member
```

Also assert quick-entry card text still has no goal progress (existing card tests stay green — add regression asserting `"Цель"` not in format_card output for normal expense).

- [ ] **Step 2:** FAIL (no hook).

- [ ] **Step 3: Implement** hooks. Keep commits ordered: transaction commit first, then check (check may commit crossed flag). Prefer: flush+commit transaction, then `await check_goal_achievement(...)`.

- [ ] **Step 4:** PASS + full pytest.

- [ ] **Step 5: Commit** `feat(goals): check achievement after balance changes`

---

### Task 5: `has_active_goal` on wallet list (settings mark data)

**Files:**
- Modify: `backend/app/schemas/wallets_categories.py` — `has_active_goal: bool`
- Modify: `backend/app/api/v1/wallets.py` — populate via subquery/exists of active goals
- Modify: `frontend/src/api/wallets.ts` — type field
- Modify: `frontend/src/pages/settings/WalletsSettingsPage.tsx` — subtitle
- Test: backend list assertion + frontend vitest for subtitle helper

**Interfaces:**
- `WalletResponse.has_active_goal: bool`
- Settings subtitle helper:

```typescript
export function formatWalletSettingsSubtitle(currency: string, hasActiveGoal: boolean): string {
  return hasActiveGoal ? `${currency} · цель` : currency
}
```

Only on Settings → Кошельки rows (shared). Default-wallet page and quick-entry pickers: **do not** show the mark.

- [ ] **Step 1: Failing tests** (API + `formatWalletSettingsSubtitle` vitest).

- [ ] **Step 2–4:** Implement until green.

- [ ] **Step 5: Commit** `feat(settings): mark wallets that carry an active goal`

---

### Task 6: Frontend Goals page + form (design one-to-one)

**Files:**
- Create: `frontend/src/api/goals.ts`
- Create: `frontend/src/components/goals/goalProgress.ts` (+ `.test.ts`)
- Create: `frontend/src/components/goals/GoalCard.tsx`
- Create: `frontend/src/components/goals/GoalFormSheet.tsx`
- Modify: `frontend/src/pages/GoalsPage.tsx`
- Modify: `frontend/src/i18n/locales/ru.json` — keys under `goals.*`
- Modify/create CSS (follow existing page CSS patterns, e.g. `HomePage` / analytics tabs)

**Interfaces:**
- API client: `listGoals(status)`, `createGoal`, `patchGoal`, `closeGoal`
- `goalProgress.ts` pure helpers mirroring design:

```typescript
export function goalLeftLine(opts: {
  done: boolean
  balance: number
  target: number
  currency: 'UZS' | 'USD'
}): string | null
// done → 'Показатели заморожены'
// balance > target → `Накоплено на ${formatGoalMoney(balance-target, currency)} больше`
// balance === target → null
// else → `Осталось ${formatGoalMoney(target-balance, currency)}`

export function formatGoalMoney(amount: number, currency: 'UZS' | 'USD'): string
// UZS: `{grouped} сум` (thin space optional); USD: `${grouped} $` or `$`+grouped per design home — for goals design uses nf+сум; use `N сум` / `N $`

export function goalDueLabel(deadline: string | null, closedAt: string | null, done: boolean): string
// done → `закрыта DD.MM.YYYY`
// no deadline → `без срока`
// else → `до DD.MM.YYYY`
```

- GoalsPage:
  - Header `Цели` + owner-only `Новая цель` (outline button)
  - Tabs `В процессе` / `Достигнутые` (same chip pattern as analytics tabs / design)
  - Empty active: icon placeholder, `Целей пока нет`, subtitle, owner-only `Создать цель` primary
  - Cards per design (name, pct/`Закрыта`, bar if active, saved/из target, left/due, close button if owner && balance > target, member note if !owner && balance > target)
  - Close on card calls `closeGoal`
  - Tap card (owner, active) opens edit form (wallet locked)
- GoalFormSheet fields (design labels exact):
  - `Кошелёк · обязательно` (picker of shared wallets without an active goal — or all shared for edit locked)
  - `Целевая сумма · обязательно` + currency suffix from selected wallet
  - hint `Валюта цели = валюта кошелька`
  - `Название · необязательно` hint `По умолчанию — имя кошелька`
  - `Срок · необязательно`
  - primary `Создать цель` / save for edit
- Member: no `Новая цель`, no empty-state create, no close button; when over target show note `Закрыть цель может только владелец бюджета.`

- [ ] **Step 1: Vitest** for `goalLeftLine` / owner visibility helpers — FAIL then implement.

- [ ] **Step 2: Implement UI** matching design spacing/type.

- [ ] **Step 3:** `cd frontend && npx vitest run --reporter=dot` green.

- [ ] **Step 4: Commit** `feat(goals): Цели tab list form and progress UI`

---

### Task 7: Final verification + acceptance glue

**Files:**
- Any gaps from Tasks 1–6 (edit form deadline, empty closed tab, i18n keys)
- Ensure no goal UI in quick-entry / transaction forms
- Run full backend + frontend suites; fix regressions only

- [ ] **Step 1:** `cd backend && ./venv/bin/pytest -q` — all green; capture output for final report.

- [ ] **Step 2:** `cd frontend && npx vitest run --reporter=dot` — all green; capture output.

- [ ] **Step 3:** Manual checklist against phase acceptance §2 (code-level): create default name; member no create; crossing fan-out; over-copy; re-cross; close freeze; past deadline editable; settings mark only.

- [ ] **Step 4: Commit** if any fixes: `test(goals): phase 8 acceptance coverage` or `fix(goals): …`

- [ ] **Step 5:** Stop. Do not start Phase 9.

---

## Self-review (plan vs spec)

1. **Spec coverage:** create/default name, member absent controls, achievement fan-out + owner button, progress/over/exact-100%, re-cross state, close freeze/free wallet, past deadline editable, settings-only mark, no quick-entry progress, shared-only — all tasked.
2. **Placeholders:** none intentional.
3. **Types:** `GoalResponse` fields consistent across Task 2–6; `has_active_goal` Task 5; `crossed` Task 3.
4. **Open appearance call (resolved in plan):** settings mark text ` · цель` — not in design file; required by PRD §12.5. Card close button when `balance > target` per design (`over`); Telegram close always on achievement for owner; API close anytime for active goal (owner).
