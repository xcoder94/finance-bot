# Task 13 — API: Family Members

Depends on: Task 03 (`03-bot-onboarding.md` — done, invite_token + bot-only
invite flow already exist), Task 01 (`01-auth-telegram.md` — auth deps)
PRD reference: §3, §8

## Goal

Expose family member management over HTTP, so the Settings screen
(Task 14) can list members, show/regenerate the invite link, and remove
a member — none of this currently exists as an API; it only exists
inside the Telegram bot (`backend/bot/onboarding.py`).

This task does NOT touch the bot's existing `/start` deep-link join flow
or the `/invite` bot command — both keep working exactly as they do
today. This task only adds a parallel HTTP API surface reading/writing
the same `family_budgets.invite_token` column and `users` table.

## Endpoints

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/api/v1/members` | Owner, Member | Returns non-deleted users in caller's `family_budget_id`: `id`, `first_name`, `username`, `role` |
| GET | `/api/v1/members/invite-link` | Owner | Returns the current invite link built from `family_budgets.invite_token`, same format as the bot's `/invite` command (`build_invite_link`, reuse the existing helper from `bot/onboarding.py` — do not duplicate the URL-building logic) |
| POST | `/api/v1/members/invite-link/regenerate` | Owner | Generates a new `invite_token` (`secrets.token_urlsafe(16)`, same method as bot onboarding), overwrites `family_budgets.invite_token`, returns the new invite link. The previous link stops working immediately — no history of old tokens kept |
| DELETE | `/api/v1/members/{id}` | Owner | Soft-deletes the target user (`is_deleted = true`, `deleted_at = now()`). See rules below |

## DELETE rules

- If `{id}` equals the caller's own user id → `400`
  (`{"detail": "cannot_remove_self"}`). This is a defense-in-depth
  check — the frontend must never render a delete action on the
  Owner's own row in the first place (Task 14 concern), but the API
  enforces it independently in case of a direct request.
- If `{id}` does not resolve to a non-deleted user in the caller's
  `family_budget_id` → `404` (covers already-removed users and
  cross-family access, consistent with the 404 pattern in
  `04-api-wallets-categories.md`).
- No cascade to `transactions` — historical records keep
  `created_by_user_id` unchanged, per PRD §8.
- Removing a user does not touch `family_budgets.invite_token` — the
  existing link keeps working for anyone else invited later.

## Permission enforcement

Reuses `OwnerUserDep` (already used in `wallets.py`/`categories.py`) for
all three Owner-only endpoints. `GET /members` uses `CurrentUserDep`
(Owner or Member), same pattern as `GET /wallets`.

All endpoints scope by caller's `family_budget_id`.

## Response schemas

New file `app/schemas/members.py`:

- `MemberResponse`: `id` (UUID), `first_name` (str | None), `username`
  (str | None), `role` (str)
- `InviteLinkResponse`: `invite_link` (str)
- `MemberDeleteResponse`: `id` (UUID), `first_name` (str | None),
  `role` (str)

## Implementation notes

- New router file `app/api/v1/members.py`, registered in `app/main.py`
  alongside the existing routers.
- Reuse `build_invite_link(bot_username, invite_token)` from
  `bot/onboarding.py` — import it rather than reimplementing string
  formatting, to avoid the two link formats drifting apart. If direct
  import creates a circular dependency between `app/` and `bot/`, move
  `build_invite_link` to a shared location (e.g. `app/services/`) and
  have `bot/onboarding.py` import it from there instead — do not keep
  two separate implementations.
- Token generation for regenerate must use the same method already
  used in bot onboarding (`secrets.token_urlsafe(16)`) for consistency.

## Acceptance criteria

- [ ] `GET /api/v1/members` returns all non-deleted users in the
      caller's family, both for Owner and Member callers
- [ ] `GET /api/v1/members/invite-link` returns a link matching the
      existing `family_budgets.invite_token`, in the same format the
      bot's `/invite` command produces
- [ ] `POST /api/v1/members/invite-link/regenerate` changes
      `invite_token` in the DB and returns a new, different link
- [ ] After regeneration, the OLD invite link's token no longer
      resolves via `get_family_budget_by_invite_token` (i.e. the bot's
      `/start invite_<old_token>` flow would now reject it)
- [ ] `DELETE /api/v1/members/{id}` soft-deletes the target user,
      returns `affected` fields, target disappears from `GET /members`
- [ ] `DELETE /api/v1/members/{own_id}` → `400`
- [ ] `DELETE` on already-deleted or nonexistent id → `404`
- [ ] Member role → `403` on invite-link GET, regenerate, and DELETE
- [ ] Cross-family-budget id on DELETE → `404`
- [ ] Existing bot `/start` deep-link join and `/invite` command still
      work unchanged (regression check — run
      `backend/tests/test_onboarding.py`, must stay 17/17 pass)

## Verification

1. As Owner: `GET /members` → confirm own row + any existing Member
   rows, correct `role` values.
2. As Owner: `GET /members/invite-link` → confirm it matches the link
   the bot's `/invite` command currently returns for the same family.
3. As Owner: `POST /members/invite-link/regenerate` → confirm response
   link differs from step 2; re-run `GET /members/invite-link` →
   confirm it now returns the NEW link.
4. Attempt `/start invite_<old_token>` in the bot (the token from
   before regeneration) → confirm it's rejected as invalid, same as
   any unknown token today.
5. As Member: attempt `GET /members/invite-link`,
   `POST .../regenerate`, `DELETE /members/{id}` → confirm `403` on
   all three.
6. As Owner: `DELETE /members/{own_id}` → confirm `400`.
7. As Owner: `DELETE /members/{existing_member_id}` → confirm `200`,
   member disappears from subsequent `GET /members`, their existing
   transactions in `psql` still show unchanged `created_by_user_id`.
8. Repeat step 7's DELETE on the same id → confirm `404`.
9. Run `backend/tests/test_onboarding.py` → confirm still 17/17 pass
   (no regression to bot onboarding flow).

## Changelog

Implemented 2026-07-21.

### Files added
- `backend/app/schemas/members.py` — `MemberResponse`, `InviteLinkResponse`,
  `MemberDeleteResponse`
- `backend/app/api/v1/members.py` — four endpoints (`GET /members`,
  `GET /members/invite-link`, `POST /members/invite-link/regenerate`,
  `DELETE /members/{id}`)
- `backend/app/services/invite.py` — shared `build_invite_link` helper
- `backend/tests/test_members.py` — 9 tests covering all acceptance criteria

### Files modified
- `backend/app/main.py` — registered `members_router`
- `backend/bot/onboarding.py` — imports `build_invite_link` from
  `app/services/invite.py` instead of defining it locally (bot `/start` and
  `/invite` behavior unchanged)

### Shared helper relocation
Moved `build_invite_link` to `app/services/invite.py` proactively so the API
layer does not import from `bot/`. `bot/onboarding.py` now imports from the
shared location — no duplicate URL formatting logic.

### Test results
- `tests/test_members.py`: **9/9 passed**
- `tests/test_onboarding.py`: **7/7 passed** (regression — bot onboarding
  helpers and seed-data tests unchanged; task doc mentions 17/17 but the file
  currently collects 7 tests)
- Full backend suite (`tests/`): **77/77 passed**

### Deviations
None. Bot username for invite-link endpoints is fetched via
`Bot.get_me()` (same source as `/invite`), patched in tests via
`get_bot_username` mock — avoids live Telegram calls in CI.

### Bot username caching (2026-07-21)
Replaced per-request `Bot.get_me()` calls in invite-link endpoints with a
username cached at application startup. `init_bot_username()` runs once in
the existing `lifespan` handler in `app/main.py`; `get_bot_username()` in
`app/api/v1/members.py` reads the module-level cache and returns `500` if
unavailable (no fallback to a fresh Telegram API call).

### Manual verification (2026-07-22)
Ran `backend/scripts/manual_verify_members.py` against an isolated
throwaway Family Budget (not the shared 111111/222222 fixture, since
regenerate and delete are destructive operations). **21/21 checks
passed** — covers every item in "Acceptance criteria" above, plus a
DB-level check that a removed member's existing transaction keeps its
`created_by_user_id` unchanged and the member row is soft-deleted
(`is_deleted=True`, `deleted_at` set), not hard-deleted.