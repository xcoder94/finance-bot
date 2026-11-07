# Task 00 — Local Environment Skeleton

Depends on: nothing (first real task)
PRD reference: §10 (local-first for MVP)

## Goal

A minimal but fully runnable skeleton: empty FastAPI app + empty Aiogram bot + local PostgreSQL, all connected, nothing business-specific yet. This is the foundation every later task (starting with `01-auth-telegram.md`) runs inside and gets verified against.

## Scope

1. **PostgreSQL via Docker Compose** — one `docker-compose.yml` at repo root, single `postgres` service, exposes port `5432`, persists data in a named volume, credentials from `.env` (never hardcoded in the compose file).
2. **FastAPI app** (`backend/app/main.py` or similar — agent decides exact layout, but keep it inside `backend/app/`):
   - Uses **`lifespan`** context manager for startup/shutdown — do NOT use `@app.on_event`, it's removed in the installed Starlette version (1.3.1, stable 1.0 line since March 2026).
   - `GET /health` endpoint returning `{"status": "ok"}`.
   - On startup (inside `lifespan`), opens a test connection to Postgres via `asyncpg` (already in `requirements.txt`) and confirms it can connect — fail fast with a clear error if it can't.
3. **SQLAlchemy + Alembic wiring** (both already in `requirements.txt`):
   - Async engine configured (`SQLAlchemy==2.0.51` supports async), pointed at the same Postgres instance.
   - `alembic init` done, `alembic.ini` and `env.py` configured for async, one empty baseline migration that runs clean against the fresh DB. No real tables yet — that's task 02.
4. **Aiogram bot** (`backend/bot/` or similar):
   - Minimal polling bot, `/start` handler replies with `"pong"`.
   - Bot token read from `.env` via `python-dotenv` (already in `requirements.txt`).
   - No business logic — this only proves the bot process runs and can talk to Telegram.
5. **`.env.example`** committed (not `.env` itself) listing required variables with placeholder values: `BOT_TOKEN`, `DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`.
6. **Run instructions** added to `backend/README.md`: how to start Postgres (`docker compose up -d`), run migrations (`alembic upgrade head`), start the API (`uvicorn ...`), start the bot (separate process).

## Explicitly out of scope

- No real data model (task 02).
- No Telegram `initData` validation (task 01 — but note: task 01 depends on this task's FastAPI app existing).
- No frontend.

## Acceptance criteria

- [ ] `docker compose up -d` starts Postgres, no manual DB creation steps needed beyond that.
- [ ] `alembic upgrade head` runs clean against a fresh container with zero errors.
- [ ] `uvicorn app.main:app` starts without errors; `GET /health` returns `200 {"status": "ok"}`.
- [ ] FastAPI startup fails loudly (clear error message, not a silent hang) if Postgres is unreachable — proves the `lifespan` DB check actually works, not just decorative.
- [ ] Running the bot process and sending `/start` in Telegram returns `"pong"`.
- [ ] `.env.example` present and accurate; real `.env` is gitignored and cursorignored (already true from earlier setup).

## Проверка (manual, before moving to task 01)

1. Fresh clone-like test: stop and remove the Postgres container/volume, run through the full instructions in `backend/README.md` from scratch.
2. Confirm `/health` responds.
3. Stop the Postgres container, restart the FastAPI app, confirm it fails with a readable error (not a silent crash or infinite hang) — this matters because task 01's auth dependency will run on every request, and a silent DB failure mode would be hard to debug later.
4. Confirm `/start` → `"pong"` in a real Telegram chat with your bot.
