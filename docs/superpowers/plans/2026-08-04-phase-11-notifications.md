# Phase 11 — Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Worker model:** `composer-2.5` only. Do not substitute.

**Goal:** Evening reminder at 21:00 Asia/Tashkent when the family recorded nothing that day (personal counts as activity); identical weekly digest Monday 10:00 Asia/Tashkent for shared spending; two independent per-user switches; settings subtitle lists enabled names; goal achievement message stays switch-free and still delivers.

**Architecture:** Per-user boolean prefs on `users` plus per-family idempotency dates on `family_budgets`. Pure formatters + async runners for reminder and digest; a minute tick in the bot process calls runners with an injectable clock (no new packages). Settings PATCH via `/api/v1/me`; mini-app toggle rows match the design track/knob; TOC subtitle follows PRD §17.6 (enabled names joined with ` · `, not the design's "Оба включены").

**Tech Stack:** Python/FastAPI/Aiogram/Alembic/pytest; React/Vite/TypeScript/TelegramUI/Zustand/react-i18next; vitest. No new packages (no APScheduler).

## Global Constraints

- Spec: `docs/tasks/phase-11-notifications.md` + PRD §16 (16.1–16.4 + Acceptance), §12.3 (achievement text already exists — prove only), §17.6 notifications row subtitle.
- Evening reminder: 21:00 Asia/Tashkent; per family; ONLY if zero transactions that Tashkent calendar day (`is_deleted=false`); personal-wallet ops count as activity and silence everyone.
- Evening text exactly two lines; backticks around the example; `parse_mode="Markdown"` so Telegram renders monospace:
  `Сегодня не было ни одной записи.`
  `Напишите трату одной строкой — например, `продукты 150 тысяч``
- Sent to every active member with `evening_reminder_enabled=True`, not owner-only.
- Weekly digest: Monday 10:00 Asia/Tashkent; title exactly `Итоги недели`; identical body for every member (owner gets extra trailing lines appended).
- Digest covers the **previous complete Mon–Sun week** in Asia/Tashkent (the week that ended at the Monday 00:00 just passed).
- One currency block per currency with shared spending this week; UZS block first, then USD; no cross-rate sum.
- Per currency block lines (amounts via `format_amount` / `format_number` from `bot.quick_entry.cards`):
  - `Расходы: {amount}`
  - `На {delta} больше, чем на прошлой неделе` OR `На {delta} меньше, чем на прошлой неделе` (money, never percent). Omit when last week total in that currency is 0. Omit when delta is 0.
  - `Больше всего — {name}, {amount}`
- Top category = parent level; if winner name is `Покупки и досуг` (or `translation_key == "shopping_leisure"`), show that parent's largest subcategory name instead.
- Exactly one goal line: active goal with the largest positive `отложили` this week. `отложили` = sum of transfer-in amounts to the goal wallet + income on that wallet during the digest week (shared wallets only — goals are shared). Omit if none or all ≤ 0. Never invite to create a goal.
  - Line: `Цель «{name}»: отложили {set_aside}, накоплено {balance} из {target_number}` where set_aside/balance use `format_amount`, target uses `format_number` (same as achievement).
- Income never appears as digest content; personal-wallet spending excluded from all digest totals (same filter as analytics: `wallet.is_personal.is_(False)`).
- Owner-only trailing lines (one per unclosed achieved goal: `status=="active"` and `crossed==True`):
  `Цель «{name}» достигнута — можно закрыть в разделе «Цели»`
- Exactly two switches: evening reminder + weekly digest. Goal achievement has NO switch and keeps sending.
- Settings subtitle (§17.6 / hard rule 11): enabled names joined with ` · ` (U+00B7 with spaces), order evening then weekly; both off → exactly `Выключены`. Design's "Оба включены" / "Включено одно из двух" must NOT be used.
- Defaults: both switches `true` for new users (`server_default=true`).
- Scheduling must be testable with injected/frozen Tashkent clock — tests call runners/`tick` directly; do not require wall-clock 21:00/Monday.
- No new external packages. Reuse `format_amount`, `format_number`, `resolve_bot`, `get_expenses_by_category`, `get_expenses_by_subcategory`, `wallet_balance`.
- Do **not** edit `AGENTS.md`, `CLAUDE.md`, `docs/PRD.md`, `docs/design/*`, `docs/tasks/*`.
- Worker: `composer-2.5` only. Branch: `mvp2/phase-11-notifications` (already checked out).
- Git allowed: add, commit, status, log, diff. Forbidden: push, pull, fetch, stash, checkout, switch, restore, reset, revert, branch, merge, rebase, clean, cherry-pick, tag, remote.
- Baseline must still pass: backend 336 pytest; frontend 196 vitest / 37 files.
- Stop at end of Phase 11 — no Phase 12, `/start` rewrite, release announcement, voice, photo, caching.
- User-facing Russian verbatim. Forbidden words: ошибка, сессия, сервер, токен, запрос.
- Confidence below average → write «not sure», do not guess.
- Conversation/report language with customer is Russian; this plan is English (docs/).

## File map

| File | Responsibility |
|------|----------------|
| `backend/alembic/versions/q7f8a9b0c1d2_notification_prefs.py` | User prefs + family idempotency dates |
| `backend/app/models/user.py` | `evening_reminder_enabled`, `weekly_digest_enabled` |
| `backend/app/models/family_budget.py` | `last_evening_reminder_on`, `last_weekly_digest_on` |
| `backend/app/schemas/auth.py` | Expose prefs on `MeResponse` / `MeUpdate` |
| `backend/app/api/v1/me.py` | GET/PATCH prefs |
| `backend/app/services/evening_reminder.py` | Activity check, exact text, fan-out |
| `backend/app/services/weekly_digest.py` | Week windows, currency blocks, goal line, owner trailing, fan-out |
| `backend/app/services/notification_scheduler.py` | `is_*_time`, `tick`, idempotent runners |
| `backend/bot/main.py` | Background minute loop calling `tick` |
| `backend/tests/test_evening_reminder.py` | Activity / silence / text / switches / clock |
| `backend/tests/test_weekly_digest.py` | Structure cases from acceptance |
| `backend/tests/test_notification_scheduler.py` | Frozen-clock tick / idempotency |
| `backend/tests/test_notification_prefs_api.py` | PATCH/GET prefs |
| `backend/tests/test_phase8_goals.py` | Keep existing achievement tests green (no rewrite of notify text) |
| `frontend/src/components/settings/SettingsToggleRow.tsx` | Design toggle track/knob |
| `frontend/src/index.css` | Toggle styles matching design sizes |
| `frontend/src/pages/settings/NotificationsSettingsShellPage.tsx` | Wire toggles to PATCH |
| `frontend/src/utils/settingsSubtitles.ts` | Dynamic notifications subtitle |
| `frontend/src/api/me.ts` + `authStore.ts` | Pref fields |
| `frontend/src/pages/SettingsPage.tsx` | Pass prefs into subtitle |
| Frontend tests | Toggle + subtitle + me mapping |

---

### Task 1: Preference storage and `/me` API

**Files:**
- Create: `backend/alembic/versions/q7f8a9b0c1d2_notification_prefs.py`
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/models/family_budget.py`
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/api/v1/me.py`
- Test: `backend/tests/test_notification_prefs_api.py`

**Interfaces:**
- Produces:
  - `User.evening_reminder_enabled: bool` (default/server_default `true`)
  - `User.weekly_digest_enabled: bool` (default/server_default `true`)
  - `FamilyBudget.last_evening_reminder_on: date | None`
  - `FamilyBudget.last_weekly_digest_on: date | None`
  - `MeResponse.evening_reminder_enabled: bool`
  - `MeResponse.weekly_digest_enabled: bool`
  - `MeUpdate.evening_reminder_enabled: bool | None = None`
  - `MeUpdate.weekly_digest_enabled: bool | None = None`
- Consumes: existing `create_user_with_budget`, `api_client`, `auth_headers` from `tests.test_wallets_categories`.

- [ ] **Step 1: Write failing API tests**

```python
import socket
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_wallets_categories import api_client, auth_headers, create_user_with_budget


def _db_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            return True
    except OSError:
        return False


def _tid() -> int:
    return int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_me_defaults_notification_prefs_on(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    tid = _tid()
    await create_user_with_budget(session, telegram_id=tid, role="owner")
    await session.commit()
    r = await client.get("/api/v1/me", headers=auth_headers(tid))
    assert r.status_code == 200
    body = r.json()
    assert body["evening_reminder_enabled"] is True
    assert body["weekly_digest_enabled"] is True


@pytest.mark.skipif(not _db_available(), reason="DB not configured")
@pytest.mark.anyio
async def test_patch_notification_prefs_independently(
    api_client: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = api_client
    tid = _tid()
    await create_user_with_budget(session, telegram_id=tid, role="owner")
    await session.commit()
    r = await client.patch(
        "/api/v1/me",
        headers=auth_headers(tid),
        json={"evening_reminder_enabled": False},
    )
    assert r.status_code == 200
    assert r.json()["evening_reminder_enabled"] is False
    assert r.json()["weekly_digest_enabled"] is True
    r2 = await client.patch(
        "/api/v1/me",
        headers=auth_headers(tid),
        json={"weekly_digest_enabled": False},
    )
    assert r2.status_code == 200
    assert r2.json()["evening_reminder_enabled"] is False
    assert r2.json()["weekly_digest_enabled"] is False
```

- [ ] **Step 2: Run tests — expect FAIL** (missing columns / schema fields)

Run: `cd backend && pytest tests/test_notification_prefs_api.py -q`
Expected: FAIL

- [ ] **Step 3: Migration + models + schemas + me.py**

Migration revises `p6e7f8a9b0c1`. Add columns:

```python
# users
op.add_column("users", sa.Column("evening_reminder_enabled", sa.Boolean(), nullable=False, server_default="true"))
op.add_column("users", sa.Column("weekly_digest_enabled", sa.Boolean(), nullable=False, server_default="true"))
# family_budgets
op.add_column("family_budgets", sa.Column("last_evening_reminder_on", sa.Date(), nullable=True))
op.add_column("family_budgets", sa.Column("last_weekly_digest_on", sa.Date(), nullable=True))
```

Wire ORM, `MeResponse`/`MeUpdate`, `_build_me_response`, and `patch_me` using `model_fields_set` like language.

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/q7f8a9b0c1d2_notification_prefs.py \
  backend/app/models/user.py backend/app/models/family_budget.py \
  backend/app/schemas/auth.py backend/app/api/v1/me.py \
  backend/tests/test_notification_prefs_api.py
git commit -m "$(cat <<'EOF'
feat(notifications): add per-user reminder/digest prefs on /me

EOF
)"
```

---

### Task 2: Evening reminder service

**Files:**
- Create: `backend/app/services/evening_reminder.py`
- Test: `backend/tests/test_evening_reminder.py`

**Interfaces:**
- Consumes: `User`, `FamilyBudget`, `Transaction`, `format`/`resolve_bot` patterns from `goal_notify`
- Produces:
  - `EVENING_REMINDER_TEXT: str` — exact two-line PRD text with backticks
  - `async def family_had_activity_on(session, family_budget_id, day: date) -> bool` — any non-deleted transaction whose `transaction_date` falls on that Asia/Tashkent calendar day (personal included)
  - `async def send_evening_reminders_for_family(session, budget: FamilyBudget, day: date, bot) -> int` — send to each active user with `evening_reminder_enabled`, return send count; callers handle idempotency dates
  - Day bounds: `[datetime(day, 0,0, tzinfo=TASHKENT), datetime(day, 0,0, tzinfo=TASHKENT) + timedelta(days=1))` compared against `transaction_date` (aware).

- [ ] **Step 1: Write failing tests**

```python
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.evening_reminder import (
    EVENING_REMINDER_TEXT,
    family_had_activity_on,
    send_evening_reminders_for_family,
)
from tests.test_wallets_categories import api_client, create_user_with_budget

TASHKENT = ZoneInfo("Asia/Tashkent")

EXPECTED = (
    "Сегодня не было ни одной записи.\n"
    "Напишите трату одной строкой — например, `продукты 150 тысяч`"
)


def test_evening_text_exact():
    assert EVENING_REMINDER_TEXT == EXPECTED


# Plus DB tests:
# 1) no activity → both owner+member with switch on receive exact text, parse_mode Markdown
# 2) personal-wallet expense same day → family_had_activity_on True; send returns 0 / not called when runner skips
# 3) user with evening_reminder_enabled=False does not receive; other member still does
```

Use `api_client` fixture for session; `AsyncMock` bot; create personal wallet via `Wallet(..., is_personal=True, owner_user_id=...)`.

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement `evening_reminder.py`**

```python
EVENING_REMINDER_TEXT = (
    "Сегодня не было ни одной записи.\n"
    "Напишите трату одной строкой — например, `продукты 150 тысяч`"
)
```

Fan-out: `await bot.send_message(user.telegram_id, EVENING_REMINDER_TEXT, parse_mode="Markdown")`.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(notifications): evening reminder for idle families

EOF
)"
```

---

### Task 3: Weekly digest formatters and assembly

**Files:**
- Create: `backend/app/services/weekly_digest.py`
- Test: `backend/tests/test_weekly_digest.py`

**Interfaces:**
- Consumes: `get_expenses_by_category`, `get_expenses_by_subcategory`, `format_amount`, `format_number`, `wallet_balance`, `Goal`, `Wallet`
- Produces:
  - `DIGEST_TITLE = "Итоги недели"`
  - `SHOPPING_LEISURE_NAME = "Покупки и досуг"`
  - `def digest_week_bounds(monday: date) -> tuple[datetime, datetime, datetime, datetime]`
    - Input: the Monday (Tashkent calendar date) when the digest fires.
    - Returns `(this_start, this_end, last_start, last_end)` where `this_*` is the previous Mon–Sun window:
      - `this_end = datetime(monday, 0,0, TASHKENT)` (exclusive)
      - `this_start = this_end - 7 days`
      - `last_end = this_start`
      - `last_start = this_start - 7 days`
    - Queries use `transaction_date >= start AND transaction_date < end`.
  - `def format_currency_block(*, currency, total, last_total, leader_name, leader_amount) -> str`
  - `def format_goal_line(*, name, set_aside, balance, target, currency) -> str`
  - `def format_owner_trailing(name: str) -> str`
  - `async def build_digest_body(session, family_budget_id, monday: date) -> str` — shared identical body (title + currency blocks + optional goal line); no owner trailing
  - `async def build_owner_trailing_lines(session, family_budget_id) -> list[str]`
  - `async def goal_set_aside_this_week(session, goal, start, end) -> int`
  - `async def send_weekly_digest_for_family(session, budget, monday: date, bot) -> int`

**Currency block exact formats:**

```
Расходы: {format_amount(total, currency)}
На {format_amount(abs(delta), currency)} больше, чем на прошлой неделе
Больше всего — {leader_name}, {format_amount(leader_amount, currency)}
```

(or `меньше`). Blank line between currency blocks. Goal block separated by blank line after last currency block.

**Leader selection:**
1. `cats = await get_expenses_by_category(..., currency, this_start, this_end - 1µs)` — note existing API uses inclusive `date_to`; pass `this_end - timedelta(microseconds=1)` OR adjust calls to match inclusive semantics used elsewhere in tests. Prefer matching how analytics tests pass ranges: use inclusive end = last instant of Sunday.
2. Top = first row (already ordered desc). If none, omit whole currency block (no spending).
3. If `top.category_name == "Покупки и досуг"` or `top.category_translation_key == "shopping_leisure"`: `subs = await get_expenses_by_subcategory(..., top.category_id, ...)`; leader_name = first sub name (or parent if empty — should not happen).

**Currencies order:** build UZS block if UZS shared expenses > 0; then USD if USD > 0.

**Goal line:** among `Goal.status=="active"` for the family, compute set_aside; pick max where set_aside > 0; balance via `wallet_balance(session, goal.wallet_id)`.

**Owner trailing:** active + crossed goals, one line each; order stable by name or created_at.

- [ ] **Step 1: Write failing tests covering acceptance cases**

Pure unit tests for formatters + week bounds; DB tests for:
1. Two currencies → UZS then USD, each with total/delta/leader
2. Last week USD empty → USD block present, no comparison line
3. Top parent Покупки и досуг → subcategory name in leader line
4. Income present → not in digest text
5. Personal expense → not in shared totals
6. Goal with set-aside → one goal line; zero set-aside → omitted
7. Owner trailing only when building owner message; members do not get trailing
8. Switch off → that user skipped

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(notifications): weekly digest shared spending summary

EOF
)"
```

---

### Task 4: Scheduler tick with injectable clock

**Files:**
- Create: `backend/app/services/notification_scheduler.py`
- Modify: `backend/bot/main.py`
- Test: `backend/tests/test_notification_scheduler.py`

**Interfaces:**
- Produces:
  - `def is_evening_reminder_slot(now: datetime) -> bool` — Tashkent hour==21 and minute==0
  - `def is_weekly_digest_slot(now: datetime) -> bool` — Tashkent weekday==0 (Monday), hour==10, minute==0
  - `async def tick(session, now: datetime, bot) -> None`:
    1. Convert `now` to Tashkent; `today = local.date()`
    2. If evening slot: for each non-deleted family where `last_evening_reminder_on != today`: if not `family_had_activity_on(... today)`: send; always set `last_evening_reminder_on = today` after attempting the slot (so families with activity are marked and not rechecked all night — **or** only set when sent / when evaluated). Prefer: mark evaluated date whenever the slot runs for that family so a family with activity is not re-scanned every minute. Actually loop is once per minute and slot is only minute==0, so once per day. Still set `last_evening_reminder_on = today` after processing the family in the evening slot (whether or not messages sent).
    3. If weekly slot: for each family where `last_weekly_digest_on != today`: build/send digest; set `last_weekly_digest_on = today`.
  - `async def notification_loop(bot, *, sleep_seconds: float = 60.0, clock=datetime.now)` — infinite loop for bot process; tests do not need to run the loop.

Wire in `bot/main.py`:

```python
async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    ...
    loop_task = asyncio.create_task(_run_notification_loop(bot))
    try:
        await dp.start_polling(bot)
    finally:
        loop_task.cancel()
```

`_run_notification_loop` opens `async_session_factory` sessions per tick.

- [ ] **Step 1: Failing scheduler tests with frozen datetimes**

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from app.services.notification_scheduler import is_evening_reminder_slot, is_weekly_digest_slot

TASHKENT = ZoneInfo("Asia/Tashkent")

def test_evening_slot_only_at_2100_tashkent():
    assert is_evening_reminder_slot(datetime(2026, 8, 4, 21, 0, tzinfo=TASHKENT))
    assert not is_evening_reminder_slot(datetime(2026, 8, 4, 21, 1, tzinfo=TASHKENT))
    assert not is_evening_reminder_slot(datetime(2026, 8, 4, 20, 0, tzinfo=TASHKENT))

def test_weekly_slot_monday_1000():
    # 2026-08-03 is Monday
    assert is_weekly_digest_slot(datetime(2026, 8, 3, 10, 0, tzinfo=TASHKENT))
    assert not is_weekly_digest_slot(datetime(2026, 8, 4, 10, 0, tzinfo=TASHKENT))  # Tuesday
```

Plus DB integration: at 21:00 with no activity → sends; second tick same day → no duplicate (idempotency via last_*_on); personal activity → no send; Monday 10:00 → digest sent.

- [ ] **Step 2–4: Implement, pass, commit**

```bash
git commit -m "$(cat <<'EOF'
feat(notifications): Tashkent clock tick for reminder and digest

EOF
)"
```

---

### Task 5: Frontend toggles and settings subtitle

**Files:**
- Create: `frontend/src/components/settings/SettingsToggleRow.tsx`
- Modify: `frontend/src/index.css` (toggle styles: 44×26 track, 20 knob, radius 13, on=`var(--acc)`, off=`var(--chip)`)
- Modify: `frontend/src/pages/settings/NotificationsSettingsShellPage.tsx`
- Modify: `frontend/src/utils/settingsSubtitles.ts`
- Modify: `frontend/src/utils/settingsSubtitles.test.ts`
- Modify: `frontend/src/pages/settings/notificationsSettingsShell.test.tsx` (replace "no switch" assertion with toggle behaviour)
- Modify: `frontend/src/api/me.ts`, `frontend/src/api/me.test.ts`
- Modify: `frontend/src/store/authStore.ts`
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Optional: `frontend/src/components/settings/SettingsToggleRow.test.tsx`

**Interfaces:**
- `notificationsSubtitle(eveningEnabled: boolean, weeklyEnabled: boolean): string`
  - both true → `Напоминание вечером · Итоги недели`
  - only evening → `Напоминание вечером`
  - only weekly → `Итоги недели`
  - both false → `Выключены`
- `SettingsToggleRow({ name, subtitle, enabled, onToggle })` — button `role="switch"` `aria-checked={enabled}` with class `settings-toggle-row` / track / knob; knob at flex-end when on.
- Page loads prefs from `useAuthStore` user; toggles call `patchMe({ evening_reminder_enabled })` / weekly; update store on success.
- `AuthUser` gains `eveningReminderEnabled`, `weeklyDigestEnabled`.
- Settings TOC: `notificationsSubtitle(user.eveningReminderEnabled, user.weeklyDigestEnabled)`.

- [ ] **Step 1: Failing subtitle + toggle tests**

```typescript
expect(notificationsSubtitle(true, true)).toBe('Напоминание вечером · Итоги недели')
expect(notificationsSubtitle(false, false)).toBe('Выключены')
expect(notificationsSubtitle(true, false)).toBe('Напоминание вечером')
expect(notificationsSubtitle(false, true)).toBe('Итоги недели')
```

Update notifications body test: expect `role="switch"` present (two switches); no third switch; titles unchanged.

- [ ] **Step 2–4: Implement to match design sizes; pass; commit**

```bash
git commit -m "$(cat <<'EOF'
feat(settings): notification toggles and dynamic subtitle

EOF
)"
```

---

### Task 6: Goal achievement regression + full suite gate

**Files:**
- Test only (reuse `backend/tests/test_phase8_goals.py`); add thin regression in `backend/tests/test_evening_reminder.py` or new `backend/tests/test_goal_achievement_no_switch.py` if clearer:
  - Crossing still fans out via `format_achievement_message` / `fan_out_achievement`
  - Prefs `evening_reminder_enabled=False` and `weekly_digest_enabled=False` do **not** block achievement sends
- Do **not** rewrite `goal_notify.py` text.

- [ ] **Step 1: Write failing test that achievement sends despite both switches off**

- [ ] **Step 2–4: Confirm existing code already passes (no switch check in goal_notify); commit if new test file added**

- [ ] **Step 5: Run full suites**

```bash
cd backend && pytest -q
cd frontend && npx vitest run --reporter=dot
```

Expected: backend ≥ 336 passing; frontend ≥ 196 across ≥ 37 files. Fix any regressions before finishing.

- [ ] **Step 6: Final commit if needed for test-only additions**

```bash
git commit -m "$(cat <<'EOF'
test(notifications): prove goal achievement ignores switches

EOF
)"
```

---

## Self-review

1. **Spec coverage:** §16.1 evening → Tasks 2+4; §16.2 digest+goal line+owner trailing → Task 3+4; §16.3/12.3 achievement → Task 6; §16.4/17.6 switches+subtitle → Tasks 1+5; frozen clock → Task 4; personal silences reminder / excluded from digest → Tasks 2+3; no third reminder → enforced by only two runners.
2. **Placeholders:** none intended — concrete strings, signatures, commands.
3. **Types:** prefs names consistent across User/MeResponse/MeUpdate/AuthUser/patchMe.

## Execution notes for orchestrator

- Use `composer-2.5` implementers only.
- Prefer subagent-driven-development: one task per implementer, review between tasks.
- After all tasks: produce the phase OUTPUT report only (raw git/tests + ACCEPTANCE lines).
