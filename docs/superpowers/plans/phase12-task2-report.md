# Phase 12 Task 2 — Report: release announcement delivery marker (migration + model)

## Summary

Added nullable timezone-aware `users.release_announcement_delivered_at` via Alembic revision `r8a9b0c1d2e3` (revises `q7f8a9b0c1d2`) and mapped `User.release_announcement_delivered_at: datetime | None` on the ORM model. Column smoke test added to `test_phase12_bot_chrome.py`.

## Tests

### Before implementation

```text
pytest tests/test_phase12_bot_chrome.py::test_user_has_release_announcement_delivered_at_column -q
1 failed — AttributeError: release_announcement_delivered_at (column missing on User)
```

### After implementation

```text
alembic upgrade head
Running upgrade q7f8a9b0c1d2 -> r8a9b0c1d2e3, release announcement delivery marker on users

pytest tests/test_phase12_bot_chrome.py::test_user_has_release_announcement_delivered_at_column -q
1 passed

pytest tests/test_phase12_bot_chrome.py -q
9 passed

pytest -q
376 passed
```

(+1 test vs Task 1 baseline 375)

## Changes

| File | Change |
|------|--------|
| `backend/alembic/versions/r8a9b0c1d2e3_release_announcement.py` | New migration: `release_announcement_delivered_at` timestamptz nullable on `users` |
| `backend/app/models/user.py` | `DateTime(timezone=True)` ORM column `release_announcement_delivered_at` |
| `backend/tests/test_phase12_bot_chrome.py` | `test_user_has_release_announcement_delivered_at_column` |

## Interfaces produced

- `User.release_announcement_delivered_at: datetime | None` (timezone-aware)
- Alembic revision `r8a9b0c1d2e3` revises `q7f8a9b0c1d2`

## Disabled / stubbed / mocked

None.

## Notes

- Task 3 (service, CLI, delivery tests) not implemented — out of scope.
- Migration applied locally with `alembic upgrade head` in venv.
