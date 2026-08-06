# Phase 16g — cascade fallback logging (data collection only, no behavior change)

Branch: `mvp2/phase-16-cascade-demo-protected-support` (continue on it, no
new branch).
Orchestrator: Cursor Grok 4.5. Workers: `composer-2.5` only.

Full spec: `docs/context/mini-prd-cascade-fallback-log.md` — read it in
full before starting, this file is the task framing, that file is the
detail.

Report at `docs/cursor/reports/phase-16g-cascade-fallback-log.md` — same
format as every phase-16 round: tests before/after, disabled/mocked
list (say "none" if empty), files touched.

---

## Goal

Every quick-entry text message that the cascade prefilter
(`try_prefilter`) cannot resolve today falls through to the LLM parser,
silently. We want a passive record of those messages so the PM can
review them periodically and grow `CASCADE_KEYWORDS` over time. **This
is pure data collection — the bot's behavior, replies, and the LLM
fallback itself must not change in any way.** No new user-facing text,
no new button, no new command.

## Scope

Only `backend/bot/quick_entry/handlers.py`,
`process_quick_entry_text` — the one call site where
`try_prefilter` runs (`prefilter_enabled=True`, currently line 688).
Voice and receipt-photo entry never call `try_prefilter` — leave them
untouched.

## What to capture

Every branch where `try_prefilter` returns `None` today, not just "no
category match" — all of them:

- `transfer_signal` — matched a wallet-transfer/exchange phrase
- `multi_operation` — more than one amount, or a multi-op connector
- `amount_not_singular` — zero or more than one amount found
- `no_category_match` — zero category keyword matches
- `category_ambiguous` — more than one category keyword matched
- `wallet_ambiguous` — more than one wallet name matched
- `prefilter_disabled` — prefilter flag off (not reachable from the
  live call site today; include for completeness)

`try_prefilter`'s current return type (`ParsedOperation | None`) must
keep working for all existing callers/tests — add a way to also report
which branch produced the `None` (e.g. a small result object, or a
second return value) without changing the actual parsing decision.
Existing prefilter tests must keep passing unmodified in behavior,
only updated for whatever new return shape you choose.

## Data model

New table, append-only, no update/delete path from the bot:

`cascade_fallback_log`
- `id` — PK
- `family_budget_id` — FK
- `telegram_user_id` — bigint
- `text` — the raw message text, verbatim, as typed by the user
- `reason` — one of the values listed above
- `created_at` — timestamptz, default now()

New Alembic migration for it.

## Where to write the row

In `process_quick_entry_text`, when `prefilter_hit` is `False`, insert
one row **before** the daily model-call-limit check (`can_model_call`)
— so messages that get throttled by the daily limit are captured too,
not only ones that actually reach the LLM. Wrap the insert in
try/except so a logging failure can never block the reply to the user
— same best-effort pattern as the phase-16d error logging
(`backend/app/logging_setup.py`) already on this branch.

Log the full raw text, not an extracted keyword — out-of-context single
words can be ambiguous (e.g. "автобус" could inform either the
`transport` parent category or its `public_transport` child), the PM
needs the whole sentence to make a correct call later. Do not dedup or
count at write time — one row per occurrence; aggregation happens later
at review time, outside this task.

## Explicitly not part of this task

- No dashboard, no bot command, no admin screen to browse the log.
- No change to `CASCADE_KEYWORDS` itself.
- No change to what the user sees or how the LLM fallback behaves.
- No retention/cleanup job for the table.

---

## Constraints, same as every phase-16 round

- Full test run before and after, exact numbers, both backend and
  frontend.
- List everything disabled/stubbed/mocked — say "none" if empty.
