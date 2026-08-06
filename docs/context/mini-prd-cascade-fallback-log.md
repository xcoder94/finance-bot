# Mini-spec — cascade fallback logging (data collection only)

## Goal

Capture every quick-entry text message the cascade prefilter could not
resolve, so the keyword dictionary (`CASCADE_KEYWORDS`) can be reviewed
and extended periodically ("раз в N дней"), gradually shrinking the
share of messages that need an LLM call. **Pure data collection — the
bot's behaviour does not change.** The LLM parser still runs exactly as
it does today for every unresolved message; this only adds a passive
record for later human review.

## Scope

Text quick-entry only (`backend/bot/quick_entry/handlers.py`,
`process_quick_entry_text`), the one call site where the cascade
prefilter (`try_prefilter`) runs today (`prefilter_enabled=True`,
line 688). Voice and receipt-photo entry never call `try_prefilter` —
they always go through their own parsers — so "cascade fallback" has no
meaning there. Out of scope unless the PM asks to extend the cascade to
those paths later.

## What counts as "fell through to the LLM"

All of `try_prefilter`'s `None`-return branches, not only "category not
found" — per PM instruction, capture everything now so future cascade
work (transfers, multi-operation messages) has data to work from too:

- `transfer_signal` — message matched a wallet-transfer/exchange phrase
- `multi_operation` — more than one amount, or a multi-op connector
  ("и", "а также")
- `amount_not_singular` — zero or more than one amount found
- `no_category_match` — zero category keyword matches
- `category_ambiguous` — more than one category keyword matched
- `wallet_ambiguous` — more than one wallet name matched
- `prefilter_disabled` — prefilter flag off (not reachable today, since
  the live call site always passes `prefilter_enabled=True`; included
  for completeness/robustness)

## Data captured

New table, append-only, no update/delete from the bot:

`cascade_fallback_log`
- `id` — PK
- `family_budget_id` — FK
- `telegram_user_id` — bigint
- `text` — the raw message text, verbatim, as typed
- `reason` — one of the values above
- `created_at` — timestamptz, default now()

Log the raw text, not an extracted "word" — the earlier discussion (see
`cascade-keyword-review.md`) showed category words can be ambiguous out
of context (e.g. "автобус" could inform `public_transport` or the
`transport` parent); the full sentence is what a human needs to decide
correctly. No dedup/counting at write time — every occurrence is its own
row; aggregation (group by normalized text, sort by frequency) happens
at review time, in the query/report, not in the write path.

## Code changes

1. `backend/app/parsing/prefilter.py` — `try_prefilter` needs to also
   report *which* branch produced a `None`, without changing its
   result for the actual parsing decision. Existing tests assert on
   the `ParsedOperation | None` return value and must keep passing;
   whatever shape carries the extra reason (return a small result
   object, add a second return value, etc.) is an implementation
   decision, not a product one.
2. `backend/bot/quick_entry/handlers.py`, `process_quick_entry_text` —
   when `prefilter_hit` is `False`, insert one `cascade_fallback_log`
   row with the reason, **before** the daily model-call-limit check (so
   throttled messages are captured too, not only ones that actually
   reached the LLM). Wrap the insert in try/except so a logging failure
   can never block the reply to the user — same best-effort pattern as
   phase-16d error logging.
3. Alembic migration for the new table.

## Review flow (not built now — on demand)

No dashboard, no bot command, no admin screen. When the PM wants to
review (every N days, PM's call), the assistant queries the table,
groups by normalized text + reason, sorts by frequency, and writes a
markdown doc in the same shape as `cascade-keyword-review.md` for the
PM to annotate. Once the PM decides, the additions get transcribed into
`CASCADE_KEYWORDS` and `test_phase16_prefilter*.py` gets re-run — same
loop already in use for the keyword review.

## Open question

Which phase/task bucket does this belong to — folded into the current
`mvp2/phase-16-cascade-demo-protected-support` branch, or a new phase?
Not my call (`AGENTS.md`: slicing the PRD into phases is the PM's job).
