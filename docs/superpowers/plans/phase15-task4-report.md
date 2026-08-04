# Phase 15 — Task 4: Flag-off regression + smoke script + suite gate

**Branch:** `mvp2/phase-14b-and-15`  
**Date:** 2026-08-04

## Flag-off isolation tests added

Three tests in `backend/tests/test_phase15_receipt_photo.py`:

- `test_handlers_import_with_receipt_flag_off` — `from bot.quick_entry import handlers` with `RECEIPT_PHOTO_ENABLED=None`
- `test_voice_handler_import_with_receipt_flag_off` — `handle_quick_entry_voice` importable with flag off
- `test_receipt_photo_enabled_false_when_unset` — `receipt_photo_enabled()` is False when unset

Existing wiring tests retained:

- `test_register_bot_routers_skips_receipt_when_flag_off`
- `test_register_bot_routers_includes_receipt_when_flag_on`

## Phase 15 focused pytest

```
$ source /tmp/finance-bot-test-env.sh && cd backend && ./venv/bin/python -m pytest tests/test_phase15_receipt_photo.py -q

..................ssssss.....                                            [100%]
23 passed, 6 skipped in 3.23s
```

(6 skipped = DB acceptance tests when PostgreSQL unavailable in sandbox; pass with PG up.)

## Engineering smoke: `smoke_receipt_image.py`

**Label:** engineering smoke only — NOT the customer 20-receipt gate (pending customer).

Image: `/tmp/receipt-smoke/fake_receipt.jpg` (6159 bytes, synthetic receipt).

```
$ source /tmp/finance-bot-test-env.sh && cd backend && ./venv/bin/python scripts/smoke_receipt_image.py /tmp/receipt-smoke/fake_receipt.jpg

{
  "operations": [
    {
      "type": "expense",
      "amount": 12500,
      "currency": "UZS",
      "wallet_hint": null,
      "category": "Продукты",
      "comment": "STORE MART",
      "from_wallet_hint": null,
      "to_wallet_hint": null,
      "rate": null
    }
  ],
  "speech_status": null,
  "date_hint": "2026-08-01",
  "receipt_status": "ok"
}
operations=1
receipt_status='ok'
date_hint='2026-08-01'
exit=0
```

PARSER_* credentials present in test env (live Gemini call succeeded).

## `measure_prompt_cache.py` (informational)

```
$ source /tmp/finance-bot-test-env.sh && cd backend && ./venv/bin/python scripts/measure_prompt_cache.py

promptTokenCount=48582
cachedContentTokenCount=48512
cached_ratio=0.9986
exit=0
```

## Backend: full `pytest -q` (PG up, `all` permissions)

```
........................................................................ [ 16%]
........................................................................ [ 32%]
........................................................................ [ 48%]
........................................................................ [ 64%]
........................................................................ [ 80%]
..................................EE.................................... [ 96%]
..............                                                           [100%]
=============================== warnings summary ===============================
venv/lib/python3.14/site-packages/fastapi/testclient.py:1
  StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
ERROR tests/test_telegram_auth.py::TestMeEndpoint::test_missing_authorization_returns_401
ERROR tests/test_telegram_auth.py::TestMeEndpoint::test_invalid_authorization_returns_401
444 passed, 1 warning, 2 errors in 23.44s
```

2 errors pre-existing: `BOT_TOKEN=test-bot-token-for-pytest` fails aiogram `validate_token` at app lifespan — unrelated to phase 15.

## Frontend: `npx vitest run --reporter=dot`

```
 Test Files  37 passed (37)
      Tests  205 passed (205)
   Start at  21:48:59
   Duration  2.24s
```

No frontend file changes.

## Acceptance mapping (spec §10)

| # | Requirement | Status |
|---|-------------|--------|
| 1 | One receipt = one expense (total) | Stubbed acceptance + smoke shows 1 op |
| 2 | Category from merchant/contents | Stubbed + smoke `Продукты` |
| 3 | Comment = merchant | Stubbed + smoke `STORE MART` |
| 4 | Default wallet unless caption | Stubbed acceptance |
| 5 | Caption wallet override | Stubbed `с наличных` test |
| 6 | Date from receipt ≤31d else today | Stubbed + smoke `2026-08-01` |
| 7 | Album = N calls | Stubbed 3-photo test |
| 8 | Typing only, no interim text | Handler sends `typing` |
| 9 | 20s timeout for images | `test_http_parser_image_request_uses_20s_timeout` |
| 10 | Unreadable → §10.1 + unparsed | Stubbed acceptance |
| 11 | `RECEIPT_PHOTO_ENABLED` isolation | Flag tests + import tests + router wiring |
| 12 | Google + `PARSER_*` only | Gate tests + live smoke |

**Customer 20-receipt gate:** pending customer — not run, not claimed shipped.

## Stubbed / disabled / mocked

None in Task 4 deliverables. Phase 15 acceptance tests use `FixedParser` override and `MockTransport` (by design).

## Commit

`test: phase 15 isolation and suite gate`
