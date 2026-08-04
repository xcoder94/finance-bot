# Phase 11 Task 2 — Report: Evening reminder service

## Summary

Added `evening_reminder.py` with exact PRD two-line text, Tashkent calendar-day activity check (personal wallets included), and fan-out to active users with `evening_reminder_enabled=True` via `parse_mode="Markdown"`. Scheduler wiring deferred to Task 4.

## Tests

### Before implementation

```text
./venv/bin/pytest -q --ignore=tests/test_evening_reminder.py
338 passed

./venv/bin/pytest tests/test_evening_reminder.py -q
ERROR — ModuleNotFoundError: app.services.evening_reminder
```

### After implementation

```text
./venv/bin/pytest tests/test_evening_reminder.py -q
5 passed

./venv/bin/pytest -q
343 passed
```

(+5 tests vs Task 1 baseline 338)

## Changes

| File | Change |
|------|--------|
| `backend/app/services/evening_reminder.py` | `EVENING_REMINDER_TEXT`, `family_had_activity_on`, `send_evening_reminders_for_family` |
| `backend/tests/test_evening_reminder.py` | Exact text; no-activity fan-out; personal activity; switch-off skip; empty-day false |

## Commit

```text
feat(notifications): evening reminder for idle families
```

## Disabled / stubbed / mocked

None.

## Notes

- `family_had_activity_on` uses half-open day bounds `[00:00 Tashkent, next day 00:00 Tashkent)` on `transaction_date`.
- `send_evening_reminders_for_family` does not check activity or set `last_evening_reminder_on` — callers (Task 4 scheduler) own idempotency and skip-when-active logic.
- `day` parameter on send is accepted for scheduler API consistency but unused inside send (activity gate is external).
