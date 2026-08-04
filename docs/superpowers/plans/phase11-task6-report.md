# Phase 11 — Task 6 report: Goal achievement regression + full suite gate

## Scope

Prove §12.3 / §16.3 goal achievement still delivers when both notification switches are off, and has no switch of its own. No changes to `goal_notify.py`.

## Implementation

Added `backend/tests/test_goal_achievement_no_switch.py` with `test_achievement_sends_despite_both_notification_switches_off`:

1. Owner and member have `evening_reminder_enabled=False` and `weekly_digest_enabled=False`.
2. Creating a goal that crosses the threshold fans out `bot.send_message` to every member.
3. Message text matches `format_achievement_message("Накопления", 8_200_000, 8_000_000, "UZS")` exactly.
4. Owner receives the «Закрыть цель» inline keyboard; member receives no keyboard.
5. Goal is marked `crossed=True`.

Existing `fan_out_achievement` in `goal_notify.py` already has no preference checks — test confirms behaviour without code changes.

## Tests — before (phase start baseline)

```bash
cd backend && ./venv/bin/pytest -q
```

```
366 passed, 1 warning in 21.04s
```

```bash
cd frontend && npx vitest run --reporter=dot
```

```
Test Files  37 passed (37)
     Tests  198 passed (198)
```

## Tests — after Task 6

```bash
cd backend && ./venv/bin/pytest -q
```

```
367 passed, 1 warning in 21.29s
```

```bash
cd frontend && npx vitest run --reporter=dot
```

```
Test Files  37 passed (37)
     Tests  198 passed (198)
```

New test only: `tests/test_goal_achievement_no_switch.py` (+1 backend test).

## Migration

Not required — `alembic upgrade head` not run; suites green without it.

## Disabled / stubbed / mocked

None.

## Commit

```
test(notifications): prove goal achievement ignores switches
```

File: `backend/tests/test_goal_achievement_no_switch.py`
