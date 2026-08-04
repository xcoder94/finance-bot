# Phase 12 Task 3 — Report: release announcement service + CLI script + delivery tests

## Summary

Added `RELEASE_ANNOUNCEMENT_TEXT` (exact PRD §18.4), `eligible_users` / `send_release_announcements` in `app.services.release_announcement`, and customer-fired CLI `scripts/send_release_announcement.py` (`--cutoff` ISO-8601, `--dry-run`). Sends with `parse_mode="Markdown"` and `open_app_keyboard()` when URL present; marks `release_announcement_delivered_at` per user after each successful send. Not wired to `bot.main`, scheduler, lifespan, or migrations.

## Tests

### Before implementation

```text
pytest tests/test_phase12_bot_chrome.py -q
1 error during collection — ModuleNotFoundError: app.services.release_announcement
```

### After implementation

```text
pytest tests/test_phase12_bot_chrome.py -q
14 passed

pytest -q
381 passed

cd frontend && npx vitest run --reporter=dot
37 files, 205 passed
```

(+5 tests vs Task 2 baseline 376)

## Changes

| File | Change |
|------|--------|
| `backend/app/services/release_announcement.py` | §18.4 text, eligibility query, send+mark helpers |
| `backend/scripts/send_release_announcement.py` | CLI `--cutoff` / `--dry-run`; uses `BOT_TOKEN`, `async_session_factory`, `dispose_engine` |
| `backend/tests/test_phase12_bot_chrome.py` | Announcement text, send-once, after-cutoff skip, dry-run, script-not-wired tests |

## Interfaces produced

- `RELEASE_ANNOUNCEMENT_TEXT: str`
- `async def eligible_users(session, cutoff) -> Sequence[User]`
- `async def send_release_announcements(session, bot, cutoff, *, dry_run=False, now=None) -> int`
- CLI: `python scripts/send_release_announcement.py --cutoff ISO8601 [--dry-run]`

## Test note

Added `_mark_prior_users_delivered()` in announcement DB tests: marks committed fixture users inside the `api_client` transaction before creating the test user, so eligibility counts only the in-test user when the dev DB holds persistent fixture rows (e.g. Owner `111111`). Rolls back with the fixture; not required on an empty DB.

Review fix: `test_announcement_sent_once_then_skipped` patches `bot.onboarding.MINI_APP_URL` and asserts `reply_markup` is a `ReplyKeyboardMarkup` with one `Открыть приложение` button. Added `test_soft_deleted_user_skips_announcement` for `is_deleted=True` users.

## Disabled / stubbed / mocked

- Telegram `bot.send_message` mocked via `AsyncMock` in delivery tests.

## Notes

- Announcement not sent in production — manual script only (Phase 12 stop rule).
- Frontend untouched (205 / 37).
