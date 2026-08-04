# Handoff — Phase 13 (prompt caching), kickoff

Last updated: 2026-08-04.

## Role change this session

From now on this Claude Code session is the architect and context manager
(previously played by a browser Claude chat). It writes phase prompts for
Cursor, reviews Cursor's reports, and maintains this file. It does not
implement MVP2 features itself. Cursor (orchestrator: Grok 4.5 High; workers:
`composer-2.5` only, `composer-2.5-fast` banned everywhere) is the
implementer, one phase per Cursor chat.

## Branch

Phase 12 (`mvp2/phase-12-bot-chrome`) is finished, green, and — per the git
command at the top of `docs/context/cursor-prompt-phase-13.md` — merged into
`main` (fast-forward, no divergent commits on `main`). Phase 13 work happens
on a new branch `mvp2/phase-13-prompt-caching`, created by that same command.
Never pushed to GitHub — deliberate.

## Baseline test counts (measured this session, before any phase 13 work)

- Backend: `382 passed, 1 warning` (warning is a pre-existing
  `httpx`/starlette deprecation notice, unrelated to this project).
- Frontend: `37 files, 205 tests`, all passed.
- Measured on `mvp2/phase-12-bot-chrome` at commit `1a23dbc`, which is what
  fast-forwards into `main`. Same numbers hold on `main` and on the new
  phase-13 branch until phase 13 changes anything.

## Phase 13 scope

PRD §20 + `docs/tasks/phase-13-prompt-caching.md`. Explicit prompt caching
for the parser call only — cost change, zero user-facing behavior change.

## Decision made this session (confirmed by the PM, scope-expanding)

Read `backend/app/parsing/http_adapter.py`, `factory.py`, `prompt.py`,
`config.py`: `HttpParser` currently supports only `provider="openai"` and
`provider="anthropic"`, with per-provider hardcoded endpoint URLs and
response-body extraction. No Google/Gemini provider exists anywhere in
`backend/` (grep-confirmed, zero hits for "google"/"gemini").

The phase-13 spec's Preconditions table names "Google" three times
(customer-provided credentials, cache-capable API). Asked the PM: this is new
provider work, not just an explicit-cache flag on an existing provider — in
scope or not? Answer: **in scope.** PM's brainstorm already settled on
`gemini 3.1 flash lite` as the model (cost reasons — other models too
expensive for them). So Phase 13 must add a Google/Gemini provider to
`HttpParser`, not only wire caching onto openai/anthropic.

Also confirmed with the PM: Cursor prompts and any documents Cursor produces
are English, always. Conversation with the PM is Russian, always. (This
matches AGENTS.md's "Documents in docs/ are in English" — the PM's one
ambiguous line this session was resolved in favor of the existing rule.)

## Closed decisions — do not reopen

- Worker model: `composer-2.5` only, exact name. `composer-2.5-fast` is
  forbidden — as worker, fallback, retry, or editor default.
- Provider/model driven only by `PARSER_PROVIDER` / `PARSER_API_KEY` /
  `PARSER_MODEL` env vars — never hard-code a model name or version string.
- Exactly one cache for the whole installation — never per-family.
- Cache is a cost optimization, never a hard dependency — a missing/expired
  cache must not break parsing; full-prompt fallback always works.
- Deploying a changed static prompt must delete the old cache, not just stop
  using it.
- No user-facing copy or behavior changes in this phase.
- Phase 12 (`/start` texts, single "Открыть приложение" keyboard, no `/menu`,
  one-shot manually-triggered release announcement script) is closed and
  merged. Do not reopen it. Firing the release announcement against real
  users is still the customer's call — nobody has been sent anything.

## Deferred / not this phase

- Per-family caches.
- Any user-facing copy change.
- Voice (§9) / receipt-photo (§10) caching — images don't benefit from this
  cache per §10.2; do not invent a second cache design for them.
- Uzbek translations.
- Making cache a hard dependency of parsing.

## Unverified by hand

Nothing yet — phase 13 implementation has not started.

## Open questions awaiting the PM's answer

None outstanding. Both kickoff questions (Cursor-prompt language;
Google/Gemini in scope) were asked and answered this session.

## Immediate next step

`docs/context/cursor-prompt-phase-13.md` is written and ready to paste into a
new Cursor chat. Its first line is the one-line git command the PM runs to
merge phase 12 into `main` and create the phase 13 branch. Nothing else is
queued.
