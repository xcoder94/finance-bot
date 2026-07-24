# Task 01 — Telegram `initData` Authentication

Depends on: Phase 0 (`00-local-env.md` — FastAPI app running, responding on `/health`)
PRD reference: §10 (Security)

## Goal

Every API request from the Mini App must carry Telegram's `initData` and be validated server-side before any business logic runs. If validation fails, reject with `401`.

## Decision (already made — do not re-litigate)

Manual implementation, not a third-party library. Reason: Telegram's signature algorithm is fixed and hasn't changed since 2022, so it can be implemented from spec + test vectors with no dependency-version risk for an agent writing this code.

## Algorithm

1. Take the raw `initData` string (a query string: `key1=value1&key2=value2...&hash=<hex>`).
2. Parse it into key-value pairs. Remove the `hash` key from the set — it is the value we're checking against, not part of the signed payload.
3. Sort the remaining keys alphabetically. Build `data_check_string` by joining `"{key}={value}"` pairs with `\n` (newline), in sorted order.
4. Compute `secret_key = HMAC-SHA256(key="WebAppData", message=<bot_token>)` → raw bytes (not hex).
5. Compute `computed_hash = HMAC-SHA256(key=secret_key, message=data_check_string)` → hex digest.
6. Compare `computed_hash` to the `hash` value from step 2 using a constant-time comparison (`hmac.compare_digest` in Python — never `==` on secret-derived values).
7. Additionally check `auth_date`: reject if `now - auth_date > 3600` seconds (1 hour TTL — product decision, not a Telegram requirement).

## Implementation notes

- Language: Python (FastAPI backend).
- Use the standard library `hmac` and `hashlib` — no new dependency needed for the crypto itself.
- Implement as a FastAPI dependency (`Depends(...)`) that:
  - Reads `initData` from the `Authorization` header, format: `Authorization: tma <initData>` (this is the convention `@tma.js/sdk-react` uses on the frontend — confirm frontend sends it this way in task 07, don't assume yet).
  - Runs the validation above.
  - On success: parses `user` field (JSON-encoded in the query string) and returns a structured object (Telegram user id, first_name, username, etc.) for downstream use (e.g. resolving which `family_budget_id` this user belongs to).
  - On failure: raises `HTTPException(status_code=401)`.
- Bot token comes from environment variable (`.env`, already gitignored per the `.gitignore` in the repo) — never hardcoded.
- Do not implement session/JWT layer in this task — that's out of scope for MVP per PRD §10, which only requires validation on every request, not a separate session token. Re-validate `initData` on each request rather than issuing your own tokens, unless a later task explicitly changes this.

## Test vectors (from Telegram's own documentation — use these, don't invent your own)

Bot token: `5768337691:AAH5YkoiEuPk8-FZa32hStHTqXiLPtAEhx8`

Raw `initData`:
```
query_id=AAHdF6IQAAAAAN0XohDhrOrc&user={"id":279058397,"first_name":"Vladislav","last_name":"Kibenko","username":"vdkfrost","language_code":"ru","is_premium":true}&auth_date=1662771648&hash=c501b71e775f74ce10e377dea85a7ea24ecd640b223ea86dfe453e0eaed2e2b2
```

Expected intermediate secret (`HMAC-SHA256("WebAppData", bot_token)`, shown as hex for debugging only — actual code uses raw bytes):
```
a5c609aa52f63cb5e6d8ceb6e4138726ea82bbc36bb786d64482d445ea38ee5f
```

Expected final result: `computed_hash` must equal `c501b71e775f74ce10e377dea85a7ea24ecd640b223ea86dfe453e0eaed2e2b2` (the `hash` value in the raw `initData` above).

Note: this specific `auth_date` (1662771648 → year 2022) will fail the 1-hour freshness check by design — write that as a **separate** test case for the freshness rule, and use a dynamically generated `auth_date` (current time) for the "should pass end-to-end" test.

## Acceptance criteria

- [ ] Unit test: valid `initData` + correct bot token → validation passes, returns parsed user object matching the test vector above.
- [ ] Unit test: same `initData` with one character changed in `hash` → validation fails.
- [ ] Unit test: same `initData` with `auth_date` older than 1 hour → validation fails (freshness check), even though the signature itself is valid.
- [ ] Unit test: malformed `initData` (missing `hash`, empty string, garbage input) → validation fails gracefully, no unhandled exception, returns 401.
- [ ] One real protected endpoint (e.g. `GET /api/v1/me`) wired to the dependency, returns 401 for bad/missing `initData`, 200 + user info for valid `initData`.

## Проверка (manual, before moving to task 02)

1. Run backend locally (`00-local-env.md` setup).
2. Run the unit test suite — all cases above pass.
3. `curl` the protected endpoint with a deliberately broken `Authorization` header → confirm `401`.
4. Generate a real `initData` string using your own bot token and Telegram's test environment (or `@tma.js/sdk-react`'s dev tools once frontend exists — for now, construct one manually using the algorithm above), `curl` the endpoint with it → confirm `200` and correct parsed user data.

## Fix: GET /api/v1/me returns app-level user data (2026-07-18)

**Problem:** the original `GET /api/v1/me` implementation returns only
`TelegramUser` — fields parsed directly from `initData` (telegram id,
first_name, username, language_code, is_premium). It does not query the
`users` table, so it cannot tell the frontend the caller's `role`
(Owner/Member) or `family_budget_id` — both required to render
role-gated UI (PRD §3) and scope future API calls.

**Fix:** `GET /api/v1/me` now looks up the corresponding `User` row by
`telegram_id` (from the validated `TelegramUser`) and returns
app-level data instead of raw Telegram fields.

### Behavior

1. `TelegramUserDep` validates `initData` as before — unchanged, `401`
   on invalid/missing `initData`.
2. Look up `User` by `telegram_id = TelegramUser.id`.
3. Not found (`telegram_id` has no `User` row — never completed
   `/start`) → `404`, body `{"detail": "not_onboarded"}`.
4. Found but `is_deleted = true` (removed member) → `403`, body
   `{"detail": "removed_from_family"}`.
5. Found and active → `200`, body per `MeResponse`:

```python
class MeResponse(BaseModel):
    id: uuid.UUID
    telegram_id: int
    family_budget_id: uuid.UUID
    role: str
    first_name: str | None
    username: str | None
    language: str
```

### Files touched

- `app/api/v1/me.py` — new lookup logic, new response model.
- `app/schemas/auth.py` (new file) — `MeResponse`.
- `backend/tests/test_telegram_auth.py` — three new cases: 404
  (no `User` row), 403 (`is_deleted=true`), 200 with full field set
  for a valid active user. Existing 401 cases unchanged.

### Out of scope for this fix

- No changes to the HMAC validation algorithm or the 1-hour freshness
  check.
- No new endpoint, no session/JWT layer (still re-validating `initData`
  per request, per the original task's decision).
- Does not touch onboarding (`bot/onboarding.py`) — assumes `User` rows
  are already created correctly by Task 03.

## Changelog

- **2026-07-18 (me-endpoint fix)**: `GET /api/v1/me` now resolves the
  authenticated Telegram user against the `users` table and returns
  `MeResponse` (`id`, `telegram_id`, `family_budget_id`, `role`,
  `first_name`, `username`, `language`) instead of raw `TelegramUser`
  fields. Returns `404` (`not_onboarded`) if no matching `User` row
  exists, `403` (`removed_from_family`) if the matching user is
  soft-deleted. New schema `app/schemas/auth.py::MeResponse`. Unit
  tests added to `backend/tests/test_telegram_auth.py` for both new
  error cases and the expanded success payload.