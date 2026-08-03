# Phase 0 — Foundation & Application Pass

PRD: §6 (Application pass). Stack: `AGENTS.md`.
Depends on: nothing (first MVP 2 phase).
Plan: `docs/superpowers/plans/2026-08-03-phase-0-foundation.md`.

---

## User goal

A person opens the mini app once, and it keeps working for the whole time it
is open and across reopenings, without depending on the age of Telegram's
`initData` snapshot.

---

## Acceptance steps I will do by hand

1. Together with the team, run the single Phase 0 verification test
   (see «How the team verifies»): it passes.
2. Open the mini app on a real Telegram client while already onboarded
   (MVP 1 user row exists). The app loads past the splash into the existing
   shell (Home or whatever currently renders) — not the failure screen.
3. Force a revoked pass on the server (team runs the revoke helper). Leave the
   app open or reopen it. Confirm: one silent retry happens first; then the
   failure screen appears with this text **exactly**, and a primary button:

   > Не удалось открыть приложение. Закройте его и откройте снова через меню
   > бота.
   >
   > [Попробовать снова]

4. Without revoking again: obtain a fresh pass (reopen from the bot menu so
   Telegram issues fresh `initData`, or use the team's re-issue path). The app
   opens normally again.
5. **Deferred to my evening checklist (PRD §22 items 1–2), not blocking Phase 0
   exit with the team:** leave the app open more than one hour and interact;
   close it, wait more than one hour, reopen. Both must work. Phase 0 ships the
   mechanism that makes those steps possible; the clock wait is mine alone.

---

## What is NOT in this phase

- Quick entry / parsing / cards (PRD §7–§10)
- Any new mini-app screen layout work (PRD §17) beyond the failure screen
- Onboarding, wallets, categories, transactions, members, goals
- Changing `/start` bot texts (PRD §18)
- Prompt caching (PRD §20)
- Removing or redesigning MVP 1 business APIs (they keep working behind the
  new pass)
- Hosting, TLS, domains, bot registration, provider keys
- Uzbek translations
- The multi-hour wait itself as a CI gate

---

## Pre-approved decisions (exact values)

These are locked for implementers unless the customer revises this spec.

| # | Decision | Exact value |
|---|----------|-------------|
| 1 | Monorepo layout | Keep `backend/`, `frontend/`, `shared/`, `docs/`. Do not recreate the skeleton from zero. |
| 2 | Stack | Unchanged: FastAPI, Aiogram, Alembic, pytest, React, Vite, TypeScript, TelegramUI, Zustand, Oxlint, react-i18next, `@tma.js/sdk-react`, PostgreSQL. |
| 3 | Pass format | JWT, algorithm **HS256**. |
| 4 | Signing secret | Env var `APP_PASS_SECRET` (required). Separate from `BOT_TOKEN`. Add to `.env.example`. |
| 5 | JWT claims | `sub` = Telegram user id as string; `uid` = internal `users.id` UUID string when the user row exists, otherwise omit `uid`; `iat`; `exp`; `jti` = new UUID4 string per issued pass. |
| 6 | Pass lifetime | **30 days** from `iat` (`exp = iat + 2_592_000`). No sliding refresh in Phase 0. |
| 7 | Issue endpoint | `POST /api/v1/auth/pass` with header `Authorization: tma <initData>`. Response JSON: `{"access_token":"<jwt>","token_type":"bearer","expires_in":2592000}`. |
| 8 | InitData at issue only | Validate Telegram HMAC signature. Reject if `auth_date` older than **86400 seconds (24 hours)** at issue time. This window applies **only** to pass issuance, not to later API calls. |
| 9 | API authentication after Phase 0 | Protected routes accept **`Authorization: Bearer <jwt>`** only. The old every-request `tma <initData>` dependency is removed from business routes. |
| 10 | Client storage | `localStorage` key exactly `chontak_app_pass`. |
| 11 | Bootstrap order | (1) If stored pass present → `GET /api/v1/me` with Bearer. Success → ready. (2) On failure of (1), **one silent retry**: clear stored pass → exchange fresh `initData` via `POST /api/v1/auth/pass` → store → `GET /api/v1/me`. (3) If (2) fails → failure screen. If no stored pass at start, go directly to exchange then `/me`, still allowing one silent retry of that whole exchange+/me sequence on failure. |
| 12 | Failure screen copy | Verbatim PRD §6 Russian text + button label `Попробовать снова`. Button is the primary action. Banned words list still applies (this copy does not use them). |
| 13 | Retry button behaviour | Runs the same bootstrap path again (attempt pass / exchange). It does **not** claim to refresh Telegram `initData`; the sentence on the screen is the fallback. |
| 14 | Revoke for acceptance | Table `revoked_app_passes(jti TEXT PRIMARY KEY, revoked_at TIMESTAMPTZ NOT NULL)`. Any Bearer pass whose `jti` is in this table is rejected with HTTP 401. Helper script or authenticated admin-only `POST /api/v1/auth/revoke` for the test user (implementer chooses script vs endpoint; must be runnable locally without production deploy). |
| 15 | `/me` behaviour | Unchanged contract for success body and for `404 not_onboarded` / `403 removed_from_family`. Only the auth dependency changes (Bearer pass instead of `tma`). |
| 16 | Distinct error screens | Pass failure uses §6 copy. `not_onboarded` and `removed_from_family` keep their existing distinct UI — they are not replaced by the §6 screen. |
| 17 | One Phase 0 automated test name | `test_application_pass_allows_api_when_init_data_is_stale` (see verification). |
| 18 | Worker model | Implementation tasks: `composer-2.5` only. |

---

## How the team verifies without me

### Single required automated test (run before calling Phase 0 done)

```bash
cd backend && pytest tests/test_application_pass.py::test_application_pass_allows_api_when_init_data_is_stale -v
```

**Expected: PASS.**

Behaviour the test must prove:

1. Build Telegram `initData` with a valid signature and `auth_date = now - 7200`
   (2 hours old).
2. Confirm that exchanging that `initData` for a pass is **rejected** (older
   than the 24h issue window? Wait - 2 hours is within 24h).

Fix the scenario:

1. Issue a pass with **fresh** `initData` (`auth_date = now`).
2. Call `GET /api/v1/me` with `Authorization: Bearer <pass>` → **200** (user
   seeded in DB).
3. Confirm `GET /api/v1/me` with `Authorization: tma <fresh initData>` → **401**
   (business routes no longer accept raw `tma`).
4. Confirm a Bearer token with a revoked `jti` → **401**.

Additional automated coverage (may live in the same file; all must pass):

- Valid signature + fresh `auth_date` → pass issued.
- Tampered `initData` hash → issue returns 401.
- `auth_date` older than 86400s → issue returns 401.
- Expired JWT (`exp` in the past) → `/me` returns 401.
- Malformed Bearer → 401.

### Frontend self-check (no customer)

1. With a valid stored pass, reload the mini app offline from Telegram — app
   reaches ready without calling the issue endpoint first (network tab).
2. Delete `localStorage.chontak_app_pass`, reload with valid `initData` — issue
   is called once, pass stored, app ready.
3. Point API at a revoked `jti` — silent retry once, then §6 screen text
   matches character for character (compare to PRD).

### Report format to customer

Per `AGENTS.md`: test run output before and after the change; list of anything
disabled, stubbed, mocked, or marked finish-later (or explicit «empty»).

---

## Preconditions: test bot, data, access

| Need | Who provides | Notes |
|------|--------------|-------|
| Local Postgres via `docker compose` | already in repo | Phase 0 does not change compose layout unless required for the revoke table migration |
| `BOT_TOKEN` in `.env` | customer | existing test bot |
| `APP_PASS_SECRET` in `.env` | customer or implementer locally | long random string; customer sets the real value on their machine |
| `MINI_APP_URL` | customer | existing tunnel/URL for the mini app |
| Onboarded user row | existing MVP 1 data or `/start` | needed for `/me` 200 in the happy path |
| Real Telegram client | customer | steps 2–4 of hand acceptance |

---

## When you must stop and ask me

- Replacing JWT with a different pass mechanism, or changing lifetime away from
  30 days.
- Storing the pass anywhere other than `localStorage` key `chontak_app_pass`.
- Keeping every-request `tma` auth alongside Bearer «just in case».
- Changing the failure-screen Russian text or adding extra UI chrome the PRD
  does not show.
- Any new external service, paid API, or new account.
- Scope beyond this phase (quick entry, new screens, etc.).
- Confidence below average on a product-visible choice — say «not sure».

---

## Mapping to PRD §6 acceptance

| PRD §6 step | Covered by |
|-------------|------------|
| Open >1 hour, still works | Mechanism in this phase; clock wait = customer §22 |
| Close, wait >1 hour, reopen | Same |
| Revoke → silent retry → exact failure screen | Hand steps 3–4 + automated revoke case |
