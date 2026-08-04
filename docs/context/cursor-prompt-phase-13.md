git checkout main && git merge --no-ff mvp2/phase-12-bot-chrome -m "Merge branch 'mvp2/phase-12-bot-chrome'" && git checkout -b mvp2/phase-13-prompt-caching

# 1. Phase title

Phase 13 — Prompt caching (PRD §20)

# 2. WHAT TO READ

Read, in this order, before writing anything:

1. `docs/tasks/phase-13-prompt-caching.md` — the full phase spec, all
   sections.
2. `docs/PRD.md`, section "## 20. Prompt caching" only (from that heading up
   to the `---` right before "## 21. What the product does NOT have"). Do
   not read any other PRD section. Do not read the whole PRD.
3. `docs/context/handoff.md` — current baseline test counts and carried-over
   decisions.
4. Current parser code, to understand what exists today (this is code, not a
   doc, read all of it): `backend/app/parsing/prompt.py`,
   `backend/app/parsing/http_adapter.py`, `backend/app/parsing/factory.py`,
   `backend/app/parsing/base.py`, `backend/app/parsing/types.py`,
   `backend/app/config.py` (the `PARSER_*` env vars).

Do not read any other file under `docs/tasks/`. Do not read `docs/design/`
— this is a backend-only, no-UI phase.

# 3. BRANCH

`mvp2/phase-13-prompt-caching`. It already exists and is checked out — the
git command above created it from `main` before this prompt was pasted to
you. Do not create another branch. Do not switch branches. Do not merge.

# 4. CARRIED OVER

Baseline test counts, measured on the commit this branch is built from,
before any phase 13 change:

- Backend: `382 passed, 1 warning` (the warning is a pre-existing
  `httpx`/starlette deprecation notice — not yours, ignore it, do not try to
  fix it).
- Frontend: `37 files, 205 tests`, all passed. This phase should not need to
  touch the frontend at all — if your plan touches `frontend/`, stop and
  say so in QUESTIONS instead of proceeding.

Test counts must only grow or stay equal, never shrink, unless you can show
in your report exactly which test you removed and why it was invalid.

Current parser architecture (read the files yourself for exact code; this is
a summary, not a substitute):

- `app/parsing/factory.py::get_parser()` returns an `HttpParser` when
  `PARSER_API_KEY` is set, otherwise an `_InactiveParser` that raises on
  every call.
- `HttpParser` (`app/parsing/http_adapter.py`) currently accepts
  `provider="openai"` or `provider="anthropic"` only. Each has a hardcoded
  endpoint URL and its own response-body extraction. There is no
  `provider="google"` (or any Gemini) branch anywhere in the codebase —
  confirmed by grep, zero hits for "google" or "gemini" in `backend/`.
- The static instruction text lives in `app/parsing/prompt.py` as
  `IMMUTABLE_PARSER_INSTRUCTIONS` — a fixed string, already free of any
  family data. The variable tail (`text`, `wallet_names`,
  `expense_category_names`, `income_category_names`) is built separately by
  `build_mutable_parser_payload()`. This existing split between static and
  mutable content is exactly what you must cache and must not break.

Confirmed with the PM this session: this phase is expected to target Google
Gemini specifically (model `gemini-3.1-flash-lite` is what the PM intends to
run, for cost reasons — configured via `PARSER_MODEL`, never hard-coded).
Adding a Gemini provider branch to `HttpParser` is in scope for this phase,
not a separate phase.

# 5. PLAN FIRST

Before writing any implementation code, write a plan using the Superpowers
writing-plans skill and commit it. The plan must explicitly cover:

- Adding a `provider="google"` branch to `HttpParser` (or an equivalent
  clean split if you decide `HttpParser` should no longer be one class for
  three providers — your call, this is implementation structure). Check the
  current Gemini API documentation for its explicit context-caching
  mechanism (how a cached content object is created, referenced by
  subsequent calls, and deleted) before writing code — do not assume a
  remembered API shape, the SDK/endpoint surface may have changed.
- How the cache is created from `IMMUTABLE_PARSER_INSTRUCTIONS` and how a
  parse call references an existing cache instead of resending the static
  text.
- A prompt-version identifier so that a changed `IMMUTABLE_PARSER_INSTRUCTIONS`
  is detected and triggers deleting the old cache and creating a new one —
  not two caches coexisting.
- The missing/expired-cache fallback path: parsing must still complete as an
  ordinary full-prompt call, and cache rebuild must happen in the
  background, not block or fail the user-facing request.
- How you will produce the "≥90% cached tokens on one measured call"
  evidence for the report, and what you will do if `PARSER_API_KEY` /
  Gemini credentials are not present in this environment (expected — you
  likely do not have them; report this as blocked, do not fake a number).
- The automated test plan from phase-spec section 5: prompt-assembly
  assertions (static blob stable, variable tail holds
  wallets/message/date, no family data ever in the static part), and a test
  that the missing-cache path still creates a transaction using a stub
  provider.

# 6. PHASE-SPECIFIC HARD RULES

1. Provider value for Gemini is exactly `"google"` (lowercase, matching the
   existing lowercase `"openai"` / `"anthropic"` convention). Document this
   value in your report so the PM can tell the customer what to set
   `PARSER_PROVIDER` to.
2. Model name/version is read only from `PARSER_MODEL` env — never
   hard-code `gemini-3.1-flash-lite` or any other model string in code.
3. The cached static content must be exactly `IMMUTABLE_PARSER_INSTRUCTIONS`
   (or its direct successor if you rename it) — no wallet name, no date, no
   member name, no message text may ever enter it. This is PRD §20.2 and
   phase-spec acceptance step 5 — write an automated test that asserts this,
   not just a manual check.
4. Exactly one cache for the whole installation, regardless of how many
   families exist. Never build or leave room for a per-family cache, even
   as an intermediate step you plan to replace later.
5. The cache is permanent and extended in the background; it is recreated
   only when the static prompt text changes. Deploying a changed prompt
   version must delete the old cache, not merely stop referencing it.
6. If the cache is missing, expired, or not yet created, parsing must still
   work as an ordinary full-prompt call. This path must never be allowed to
   fail a user's quick entry. Cover it with a test using a stub provider.
7. No user-facing text or behavior changes anywhere in this phase. This is a
   backend-only, cost-only change.
8. Voice (§9) and receipt-photo (§10) parsing are out of scope — do not add
   caching to them, do not touch their code paths.
9. Uzbek translations are out of scope, as always.
10. If real Gemini credentials are not available in this environment to
    produce the "≥90% cached tokens" evidence or run acceptance steps 1–4
    against a live provider, say so plainly, mark those items blocked in
    ACCEPTANCE, and list them under DEFERRED STUBBED OR DISABLED. Do not
    invent or approximate a token-counter number.
11. Below-average confidence on any decision — write "not sure" in your
    report instead of deciding silently.

# 7. MODEL DISCIPLINE

1. Every worker task runs on `composer-2.5`. Exactly that name.
2. `composer-2.5-fast` is FORBIDDEN — as a worker, as a fallback, as a
   retry after a failure, and as an editor default. Never select it for
   any reason.
3. If the launch tool will not accept `composer-2.5`, STOP and say so in
   the report. Do not substitute any other model silently.
4. In MODEL ROSTER name the model for every single task, one line per
   task, including any task run by the orchestrator itself.

# 8. FILES YOU MUST NOT EDIT

`AGENTS.md`, `CLAUDE.md`, `docs/PRD.md`, `docs/design/**`,
`docs/tasks/*.md`, `docs/context/handoff.md`,
`docs/context/cursor-prompt-*.md`.

# 9. GIT

Allowed: `add`, `commit`, `status`, `log`, `diff`, all scoped to
`mvp2/phase-13-prompt-caching`. Forbidden: `push`, `pull`, `fetch`, `stash`,
`checkout` to another branch, `switch`, `restore`, `reset`, `revert`,
`branch`, `merge`, `rebase`, `clean`, `cherry-pick`, `tag`, `remote`. Do not
touch `main` or any other branch.

# 10. STOP BOUNDARY

Stop at the end of this phase: plan committed, code committed, both test
suites run and reported, every acceptance item from phase-spec section 2
marked done or not-done-with-reason, report delivered in the section 11
format below. Do not start any other phase. Do not touch
`backend/bot/quick_entry/cards.py`'s existing `MINI_APP_URL` import — it is
pre-existing and out of scope here.

# 11. OUTPUT

Deliver your report in exactly this format, as plain text, no tables, full
untruncated output for every raw section:

**RAW GIT LOG** — `git log --oneline -20`, verbatim.

**RAW GIT STATUS** — `git status`, verbatim.

**RAW BACKEND TESTS** — the full, untruncated `pytest -q` output including
the final summary line (e.g. `N passed, M warnings in Ts`).

**RAW FRONTEND TESTS** — the full, untruncated `npx vitest run
--reporter=dot` output including the final summary lines (`Test Files`,
`Tests`, `Duration`).

**ACCEPTANCE** — one line per numbered item in phase-spec section 2 (items
1–5), each ending `done` or `not done — <reason>`.

**EXTRA** — anything you did beyond the phase spec, if anything. If nothing,
say so.

**DEFERRED STUBBED OR DISABLED** — every stub, mock, skipped test, or
"finish later" item. If none, say so explicitly.

**MODEL ROSTER** — one line per task naming the model that ran it, including
orchestrator-run tasks.

**QUESTIONS** — anything you are not sure about, listed one at a time. If
none, say so.
