# Phase 11 — Task 4 report: Scheduler tick with injectable clock

## Status

**Done.** `notification_scheduler.py` with slot checks, `tick`, and `notification_loop`; `bot/main.py` wires background minute loop.

## Tests

### Before change

```
cd backend && ./venv/bin/pytest tests/test_notification_scheduler.py -q
ERROR — ModuleNotFoundError: No module named 'app.services.notification_scheduler'
```

```
cd backend && ./venv/bin/pytest -q
357 passed, 1 warning in 20.59s
```

### After change

```
cd backend && ./venv/bin/pytest tests/test_notification_scheduler.py -q
8 passed, 1 warning in 3.51s
```

```
cd backend && ./venv/bin/pytest -q
365 passed, 1 warning in 21.46s
```

## Commits

```
feat(notifications): Tashkent clock tick for reminder and digest
```

Files: `backend/app/services/notification_scheduler.py`, `backend/tests/test_notification_scheduler.py`, `backend/bot/main.py`.

## Coverage

| Case | Result |
|------|--------|
| `is_evening_reminder_slot` — only 21:00 Tashkent | pass |
| `is_weekly_digest_slot` — Monday 10:00 Tashkent | pass |
| Evening tick, no activity → reminder sent | pass |
| Second evening tick same day → no duplicate for family | pass |
| Personal-wallet activity → no reminder for family | pass |
| Monday weekly tick → digest sent | pass |
| Second weekly tick same day → no duplicate | pass |
| Off-slot tick → no sends, dates unchanged | pass |

## Disabled / stubbed / mocked

None.

## Deviations / notes

- `tick` sets `last_evening_reminder_on` after evaluating each family in the evening slot (whether or not messages sent), per task brief.
- `notification_loop` commits session per tick; logs and continues on exception.
- Integration tests filter `bot.send_message` calls by test-family telegram IDs because `tick` scans all non-deleted families in the shared PostgreSQL instance.
- `notification_loop` not exercised in tests (task brief: tests call `tick` directly).

## not sure

Nothing.
