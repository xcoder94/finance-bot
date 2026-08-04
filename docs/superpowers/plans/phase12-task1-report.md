# Phase 12 Task 1 — Report: §18.1 welcome, reply keyboard, optional MINI_APP_URL, `/menu` absence

## Summary

Added `welcome_solo()` with exact PRD §18.1 text, made `MINI_APP_URL` optional in config, replaced localized open-app button with single label `Открыть приложение`, updated owner/member welcome sends in `language_callback` to use `parse_mode="Markdown"` and optional reply keyboard, removed unused `welcome_owner`/`welcome_member` MESSAGES keys.

## Tests

### Before implementation

```text
pytest tests/test_phase12_bot_chrome.py tests/test_onboarding.py -q
2 errors during collection (ImportError: welcome_solo missing)
```

### After implementation

```text
pytest tests/test_phase12_bot_chrome.py tests/test_onboarding.py tests/test_phase9_members.py -q
54 passed

pytest -q
375 passed
```

(+8 tests vs baseline 367 from new `test_phase12_bot_chrome.py` start/keyboard/menu portion)

## Changes

| File | Change |
|------|--------|
| `backend/app/services/member_texts.py` | Added `welcome_solo()`; `welcome_invited()` untouched |
| `backend/app/config.py` | `MINI_APP_URL: str \| None` — optional, no startup crash when missing/empty |
| `backend/bot/onboarding.py` | `OPEN_APP_BUTTON_LABEL`, `open_app_keyboard()` optional, `welcome_solo` + Markdown on welcomes |
| `backend/bot/membership.py` | `open_app_keyboard()` call signature (no language arg); removed unused `user_language` |
| `backend/tests/test_phase12_bot_chrome.py` | §18.1 text, keyboard, `/menu` absence, language_callback mocks |
| `backend/tests/test_onboarding.py` | Owner welcome asserts `welcome_solo()` + `parse_mode` |

## Test note

`test_menu_command_not_registered` uses `set(callback.commands)` because installed aiogram stores command names as strings, not objects with `.command` (plan snippet would raise `AttributeError`).

## Disabled / stubbed / mocked

None.

## Notes

- `/menu` handler not present in onboarding, membership, goals, or quick-entry routers (verified by test).
- `membership.py` join-accept welcome still sends `welcome_invited` without `parse_mode` — out of Task 1 scope (only `language_callback` member path specified).
- Quick-entry `cards.py` still imports `MINI_APP_URL`; untouched as specified.
