# Phase 11 — Task 3 report: Weekly digest formatters and assembly

## Status

**Done.** `backend/app/services/weekly_digest.py` and `backend/tests/test_weekly_digest.py` implemented; all acceptance cases covered.

## Tests

### Before change

```
cd backend && ./venv/bin/pytest tests/test_weekly_digest.py -q
ERROR — ModuleNotFoundError: No module named 'app.services.weekly_digest'
```

### After change

```
cd backend && ./venv/bin/pytest tests/test_weekly_digest.py -q
14 passed, 1 warning in 3.82s
```

```
cd backend && ./venv/bin/pytest -q
357 passed, 1 warning in 20.37s
```

## Commits

```
feat(notifications): weekly digest shared spending summary
```

Files: `backend/app/services/weekly_digest.py`, `backend/tests/test_weekly_digest.py`.

## Acceptance coverage

| # | Case | Result |
|---|------|--------|
| 1 | UZS then USD blocks with total / delta / leader | pass |
| 2 | USD block when last week empty — no comparison line | pass |
| 3 | Top parent «Покупки и досуг» → subcategory in leader line | pass |
| 4 | Income not in digest text | pass |
| 5 | Personal expense excluded from shared totals | pass |
| 6 | Goal line when set-aside > 0; omitted when zero | pass |
| 7 | Owner trailing only appended in `send_weekly_digest_for_family` for owner | pass |
| 8 | `weekly_digest_enabled=False` user skipped | pass |

Pure unit tests: `digest_week_bounds`, `format_currency_block`, `format_goal_line`, `format_owner_trailing`.

## Disabled / stubbed / mocked

None.

## Deviations / notes

- Scheduler (Task 4) not built — as specified.
- `send_weekly_digest_for_family` does not set `last_weekly_digest_on`; idempotency is Task 4.
- Owner trailing order: `Goal.name`, then `Goal.created_at` (stable).
- Goal `set_aside`: sum of transfer-in to goal wallet + income on goal wallet in `[start, end)` window.

## not sure

Nothing — rules taken from task brief and plan §16.2.
