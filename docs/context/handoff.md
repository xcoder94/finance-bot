# Handoff — Phase 12 (bot chrome outside quick entry)

Last updated: 2026-08-04, end of this session.

## Branch

`mvp2/phase-12-bot-chrome`. Do NOT merge to `main`, do not push, do not create
or switch branches. Working tree has one uncommitted fix (see below) about to
be committed by this handoff commit.

## Status: Phase 12 complete, verified by hand, ready to stop here

An earlier agent session (tasks 1–4, see `docs/superpowers/plans/phase12-task*-report.md`)
implemented the phase. This session independently re-audited every claim
against actual code and actual test runs (did not trust the reports). Audit
found the implementation correct against `docs/tasks/phase-12-bot-chrome.md`
section 2 and PRD §18.1–§18.4 + Acceptance, with **one small gap**, which this
session then fixed.

### The one fix made this session

`backend/bot/membership.py`, `join_accept` handler: was sending
`welcome_invited()` with `reply_markup=open_app_keyboard()` but **without**
`parse_mode="Markdown"`. The §18.2 text contains a backtick code span
(`` `такси 25 тысяч` ``) that needs Markdown parsing to render as code — it
was showing as literal backticks. Fixed by adding `parse_mode="Markdown"` to
that one `.answer()` call, matching how `language_callback` in
`backend/bot/onboarding.py` already does it. Nothing else touched.

This path (`join_accept`) is a narrow scenario: an **already-registered** user
(with their own solo budget) taps "Присоединиться" to switch into someone
else's family budget via invite link — not the main `/start`-with-invite path
tested by phase-spec acceptance item 2 (that path is `start_handler` →
`language_callback`, which already had `parse_mode` set correctly before this
session started).

## Test counts as of right now (after the fix above, this session, verified live)

- Backend: `cd backend && source venv/bin/activate && pytest -q` → **382 passed, 1 warning**
  (warning is a pre-existing `httpx`/starlette deprecation notice, unrelated).
- Frontend: `cd frontend && npx vitest run --reporter=dot` → **37 files, 205 tests, all passed**
  (frontend was not touched this phase at all).
- Postgres was up and reachable during the backend run — the DB-dependent
  tests in `tests/test_phase12_bot_chrome.py` actually executed, not skipped
  (confirmed via `alembic current` → head `r8a9b0c1d2e3`).

## What was decided and must NOT be reopened

- `/start` texts (§18.1 solo, §18.2 invited) are final, verified byte-for-byte
  against PRD. Do not reword.
- Persistent reply keyboard: **exactly one button**, label `Открыть приложение`,
  opens `MINI_APP_URL` as a Telegram WebApp button. Do not add more buttons,
  do not restore `/menu` (PRD §18.3 explicitly says `/menu` is not built).
- Release announcement (§18.4): exact text is final. Sent **once** per
  pre-cutoff user via a manually-run CLI script
  (`backend/scripts/send_release_announcement.py --cutoff ISO8601 [--dry-run]`),
  never automatically. It is confirmed NOT wired into `bot/main.py`,
  `app/main.py`, the notification scheduler, or any migration
  (grep-verified this session).
- `MINI_APP_URL` is optional in `app/config.py` (`str | None`) — app must not
  crash at startup if it's unset; when unset, `open_app_keyboard()` returns
  `None` and no keyboard is attached.
- `.env` currently has `MINI_APP_URL` set to a live trycloudflare tunnel URL —
  that's an external/ops concern, out of this agent's scope per AGENTS.md.

## Deferred / out of scope for this phase (do not pick up without asking)

- Actually firing the release announcement against production users — the
  customer decides when (PRD §22). Nobody has been sent anything.
- Uzbek translations — explicitly out of scope everywhere in this project.
- Quick-entry card texts, voice/photo, prompt caching, app-side feature tour
  (§21) — all explicitly excluded from Phase 12 spec.
- `backend/bot/quick_entry/cards.py` still imports `MINI_APP_URL` directly
  (pre-existing, untouched, not part of this phase).

## Unverified by hand (only test-verified, not manually clicked in real Telegram)

Nobody has manually run the 5 acceptance steps in
`docs/tasks/phase-12-bot-chrome.md` section 2 against a live bot/Telegram
client this session — verification here was via reading code + running
`pytest`/`vitest`. If the user wants to sign off acceptance in the literal
"I will do this by hand" sense described in the phase spec, that manual pass
against a real test bot is still pending.

## Open questions awaiting the user's answer

None outstanding. The one open question from the audit (the `join_accept`
`parse_mode` gap) was resolved this session by fixing it — no answer from
the user was received or required; the fix was mechanical and matched an
existing pattern in the same file.

## Immediate next step

Nothing is queued. Phase 12 is done pending the user's own manual
acceptance-step walkthrough (see "Unverified by hand" above) and their
decision on when to fire the release announcement script (§22, customer's
call). Do not start Phase 13 without the user's explicit go-ahead.
