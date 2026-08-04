# Phase 11 Task 1 — Report: Preference storage and `/me` API

## Summary

Added per-user notification preference columns on `users`, per-family idempotency date columns on `family_budgets`, Alembic migration `q7f8a9b0c1d2`, and exposed prefs on `GET`/`PATCH` `/api/v1/me`.

## Tests

### Before implementation

```text
pytest tests/test_notification_prefs_api.py -q
2 failed (missing schema fields / 422 on PATCH)
```

Full suite after schema/API changes but before baseline test updates:

```text
pytest -q
3 failed, 335 passed
```

Failures: exact `MeResponse` dict assertions in `test_application_pass.py` and `test_telegram_auth.py` lacked new fields.

### After implementation

```text
pytest tests/test_notification_prefs_api.py -q
2 passed

pytest -q
338 passed
```

(+2 tests vs baseline 336 from new `test_notification_prefs_api.py`)

## Changes

| File | Change |
|------|--------|
| `backend/alembic/versions/q7f8a9b0c1d2_notification_prefs.py` | Migration: user bool prefs + family date columns |
| `backend/app/models/user.py` | `evening_reminder_enabled`, `weekly_digest_enabled` |
| `backend/app/models/family_budget.py` | `last_evening_reminder_on`, `last_weekly_digest_on` |
| `backend/app/schemas/auth.py` | Fields on `MeResponse` / `MeUpdate` |
| `backend/app/api/v1/me.py` | Build response + PATCH via `model_fields_set` |
| `backend/tests/test_notification_prefs_api.py` | Defaults + independent PATCH tests |
| `backend/tests/test_application_pass.py` | Me dict assertion updated |
| `backend/tests/test_telegram_auth.py` | Me dict assertion updated |

## Migration

- Revision: `q7f8a9b0c1d2`
- Down revision: `p6e7f8a9b0c1`
- Applied locally: `alembic upgrade head` succeeded

## Disabled / stubbed / mocked

None.

## Notes

- `evening_reminder_enabled` and `weekly_digest_enabled` default `true` at DB (`server_default`) and ORM.
- Family idempotency columns are stored only; runners/scheduler are later tasks.
- Baseline `/me` tests required adding two bool fields to expected JSON (not in original task file list; needed for 338 green).
