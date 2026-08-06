# Handoff — leaked secret purged from local history, dev ports moved to 5001/5002, backend hardened for production

Last updated: 2026-08-06 (end of session — this file was fully rewritten,
not appended to; everything before this point in the file's history is
superseded).

## Read this first — current branch state

**Checked out: `main`, in sync with `origin/main` (both at `50b05ba`).**
Nothing pending to push. The PM pushed during this session (outside the
assistant's visibility — confirmed via `git fetch`, not assumed).

```
50b05ba Harden backend for production: CORS, rate limiting, prod server docs
e54a64f Switch local dev ports: backend 5001, frontend 5002
a500e2a update                                    (PM's own commit, pre-session)
024547a env example update                        (rewritten this session, see below)
b5da2f7 Remove demo transaction seeding and clear-demo feature.
```

Backend on `main`: 515 passed, 0 failed (after fixing an unmigrated local
dev DB — see below). Frontend not touched this session, not re-run.

## What happened this session, in order

1. **Explained why `.env` lives at repo root** (PM question, no change made)
   — `docker-compose.yml` and `app/config.py` both read it from there.
   Note: this was true *at the time*; see item 3 below, PM moved it since.

2. **`git push origin main` was rejected by GitHub Push Protection.**
   Root cause: `docs/app.log`, committed in `b4b00a1` ("env example
   update"), contained a real Gemini API key
   (`PARSER_API_KEY=AQ.Ab8RN6J2Eg...`) in plaintext inside a logged Google
   API request URL. This was one of 3 commits sitting locally, unpushed —
   **`origin/main` was never at risk**, confirmed via `git fetch` before
   touching anything.
   - Fixed via `git rebase -i b5da2f7` (b5da2f7 = last commit already on
     `origin/main` at the time): re-edited `b4b00a1` to `git rm
     docs/app.log`, which made the next commit (`82aa10b`, whose only
     content was deleting that same file) empty — dropped it from the
     rebase todo instead of leaving an empty commit.
   - Result: `docs/app.log` no longer exists anywhere in reachable git
     history (verified with `git log --all -- docs/app.log` → empty, and
     a full-history grep for the leaked key string → 0 hits). The file
     also doesn't exist in the working tree and was never tracked outside
     that one purged commit.
   - **The key itself was never exposed on GitHub** (origin/main didn't
     have the commit). It's still sitting in plaintext in `backend/.env`
     (gitignored, that's normal) as `PARSER_API_KEY`. Rotating it is still
     worth doing on general hygiene grounds (it did sit in a log file
     locally for "several sessions" per the previous handoff) but it is
     **not** a "this key is now public" emergency.

3. **PM moved `.env` and `docker-compose.yml` from repo root into
   `backend/`** (their own change, commit `963aaf6`, done outside this
   session before it started). Confirmed intentional when asked directly.
   `app/config.py` now does `load_dotenv(_BACKEND_ROOT / ".env")`, not
   `_REPO_ROOT`. **Root `.env` no longer exists — `backend/.env` is now
   the only one.** Docker Compose auto-reads `.env` from the same
   directory as `docker-compose.yml`, so this is self-consistent, not a
   half-done change.

4. **PM asked to move local dev ports: backend → 5001, frontend → 5002**
   (previously 8000 and 5173/whatever Vite default). Changed:
   - `frontend/vite.config.ts` — `server.port: 5002`; proxy target for
     `/api` changed from `http://127.0.0.1:8000` to `http://127.0.0.1:5001`.
   - `backend/README.md` — run/verify commands updated to `--port 5001` /
     `curl http://127.0.0.1:5001/health`.
   - Started both locally this session to confirm: backend `/health` →
     `200 {"status":"ok"}` on 5001, frontend serving on 5002. Both were
     running via `nohup` in the background at end of session (uvicorn
     `--reload`, `npm run dev`) — **these are ephemeral, will not survive
     past this session/shell**, not something a fresh session needs to
     manage.
   - Frontend has **no** `VITE_API_URL` / base-URL env var. It calls
     relative `/api/...` paths; the vite dev-server proxy above is what
     actually routes to the backend port. In production (built `dist/`,
     no vite dev server) this proxy doesn't exist — whatever serves the
     built frontend needs its own `/api` → backend rule (nginx or
     similar). Not set up, not this session's scope.
   - Committed as `e54a64f`.

5. **PM asked to bring the backend to "production ready".** Scope was
   unclear (no phase spec covers this) — asked the PM to pick from a
   checklist grounded in an actual gap-check of the code, not guesses.
   PM picked all four. Implemented:
   - **CORS** — `CORSMiddleware` added in `app/main.py` (there was none
     before — any cross-origin browser call would have failed silently).
     Allowed origins come from new `CORS_ALLOWED_ORIGINS` env var
     (comma-separated), defaulting to `[MINI_APP_URL]` if unset. No
     cookies are used (auth is a Bearer token), so
     `allow_credentials=False`.
   - **Production process model** — added `gunicorn` +
     `uvicorn.workers.UvicornWorker` as the documented prod run command
     in `backend/README.md` (new "Running the API in production"
     section), replacing bare `uvicorn --reload` (dev-only, single
     process). Worker count left as an adjustable flag
     (`2 x cores + 1` guidance) — actual value for the real server is a
     deploy-time decision, outside this assistant's scope.
   - **Rate limiting** — `slowapi`, global per-IP default limit via new
     `RATE_LIMIT_DEFAULT` env var (default `120/minute`), wired as
     middleware + exception handler (`429` on breach) in `app/main.py`.
   - **Logging** — checked first: `app/logging_setup.py` already existed
     and was already production-grade (rotating file handler, 5 MB × 5
     backups, plus console, applied to root logger, called from both
     `app/main.py` and `bot/main.py` at import time). **No change made
     here** — flagged to the PM as already done rather than redone.
   - New deps pinned in `requirements.txt` by actually installing them in
     the venv and reading the resolved versions (not assumed): `gunicorn`,
     `slowapi`, `limits`, `deprecated`, `wrapt`.
   - New env vars documented in `backend/.env.example`:
     `CORS_ALLOWED_ORIGINS`, `RATE_LIMIT_DEFAULT`.
   - Verified live with `curl`: preflight from `MINI_APP_URL`'s origin
     passes, preflight from an arbitrary origin gets `400`; firing ~130
     requests at `/health` in a loop produced `429`s once past the
     120/minute budget.
   - Committed as `50b05ba`.

6. **Test suite scare, root-caused and fixed.** First full `pytest` run
   after the above showed **320 failed / 195 passed** — looked like the
   new middleware broke everything. It didn't: one failing test's
   traceback showed `relation "family_budgets" does not exist` — the
   local Postgres container (now under `backend/docker-compose.yml`,
   different Compose project name than before the file moved in item 3)
   had a **fresh, unmigrated volume**. `alembic current` showed nothing
   applied. Ran `alembic upgrade head` (19 migrations applied cleanly),
   re-ran the suite: **515 passed, 0 failed.** Nothing to do with CORS or
   rate limiting — pure local-environment drift from the `.env`/compose
   relocation in item 3.

## Uncommitted / working-tree notes right now

- **`AGENTS.md`** — PM-only file, never staged by the assistant.
- **`docs/context/*`** — never committed (standing PM rule), this file
  included. Carried over from before, status unchanged, still open:
  - `cascade-keyword-review.md`, `mini-prd-cascade-demo-protected-categories.md`,
    `deploy-mvp2-vs-mvp1-notes.md`, `cursor-prompt-bugfix-income-type-and-demo-data-removal.md`,
    `report-income-type-and-demo-data-removal.md`,
    `cursor-prompt-phase-16e-bugfix-tx-deeplink-and-delete-card.md`,
    `cursor-prompt-phase-16g-cascade-fallback-log.md` — none touched this
    session, same open questions as last time (see previous handoff
    content in git history if needed).
- **`docs/bugs_screens/`** — still untracked, still an open call whether
  to commit. Unchanged this session.
- **`docs/app.log`** — gone. Purged from history this session (item 2
  above), doesn't exist in the working tree either. Remove this line next
  time it's confirmed still gone — keeping it one more session as a
  paper trail.
- **`.claude/`** — local tool config, never committed.
- **`frontend/dist/`** — if still present from a previous session's
  production-build test, gitignored, not touched this session.

## Open questions / next steps for a fresh session

1. **Rotate the Gemini `PARSER_API_KEY`** — not urgent (never reached
   GitHub), but it sat in a local log file across several sessions before
   being purged this session. PM's call on timing.
2. **`build:watch` convenience script** — still unanswered from a prior
   session. Remind the PM if it doesn't come up.
3. **Delete the fully-merged `fix/income-type-and-demo-data-removal`
   branch** — routine cleanup, not done.
4. **Bug B — production Gemini location block** — still open, still
   needs the PM/hosting contact. Unrelated to this session's work.
5. **`is_demo` column** — still present on `Transaction`, still not
   dropped (schema changes are a "stop and ask"). PM decision pending.
6. **Prefilter dot-as-thousands-separator bug**
   (`app/parsing/prefilter.py:44`, `_PLAIN_AMOUNT_RE`) — still diagnosed,
   still not fixed.
7. **Frontend has no `/api` proxy outside `npm run dev`** — flagged in
   item 4 above. Whenever the PM's deploy story for the built frontend
   comes up, this needs an actual answer (reverse-proxy rule or a real
   `VITE_API_URL`), not before.
8. Everything already open before this session, unchanged:
   - `uz.json` still has 2 keys in Russian
     (`settings.membersScreen.sincePrefix`, `home.personalTitle`).
   - Several other `mvp2/phase-*` branches exist locally, fully merged —
     routine cleanup, not done.
   - Customer's 18-of-20 voice-recognition gate and 20-receipt accuracy
     gate (PRD §23) — neither run yet.
   - Deploy itself (migrations, restarts, env vars on the real server) —
     still outside this assistant's scope.

## Immediate next step

Nothing blocked on the assistant. If a fresh local dev environment is
ever spun up again (new Postgres volume, moved `.env`, etc.), check
`alembic current` before assuming test failures mean broken code — item 6
above is exactly that trap.
