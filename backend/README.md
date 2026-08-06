# Backend — Local Development

Minimal FastAPI API + Aiogram polling bot + PostgreSQL. Task `00-local-env`.

## Prerequisites

- Python 3.12+ (venv already exists at `backend/venv/`)
- Docker and Docker Compose
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## First-time setup

From the **repository root**:

```bash
# 1. Copy env template and fill in your real BOT_TOKEN
cp .env.example .env
# Edit .env — set BOT_TOKEN to your token from BotFather.
# Other values can stay as-is for local dev.

# 2. Start PostgreSQL
docker compose up -d

# 3. Install Python dependencies (if not already done)
cd backend
source venv/bin/activate
pip install -r requirements.txt

# 4. Run database migrations
alembic upgrade head
```

## Running the API

From `backend/` with the venv activated:

```bash
uvicorn app.main:app --reload --port 5001
```

Verify:

```bash
curl http://127.0.0.1:5001/health
# Expected: {"status":"ok"}
```

The API verifies a PostgreSQL connection on startup (inside the FastAPI
`lifespan` handler). If Postgres is down, uvicorn exits immediately with a
clear error — it will not hang silently.

## Running the API in production

Use Gunicorn with Uvicorn workers instead of `--reload` (single process,
auto-restart on code change — not meant for production):

```bash
gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  --workers 4 \
  --bind 0.0.0.0:5001 \
  --access-logfile - \
  --error-logfile -
```

Adjust `--workers` to the host's CPU count (rule of thumb: `2 x cores + 1`).

Two env vars control the hardening added for production (see
`.env.example`):

- `CORS_ALLOWED_ORIGINS` — comma-separated list of origins allowed to call
  the API. Empty by default, which falls back to `MINI_APP_URL` alone.
- `RATE_LIMIT_DEFAULT` — per-IP request limit applied to every route,
  e.g. `120/minute`. Requests over the limit get `429 Too Many Requests`.

Logging (console + rotating file, 5 MB x 5 backups) is already wired via
`app/logging_setup.py` and used by both the API and the bot — no
additional setup needed.

## Running the bot

In a **separate terminal**, from `backend/` with the venv activated:

```bash
python -m bot.main
```

Open your bot in Telegram and send `/start`. Expected reply: `pong`.

## Stopping services

```bash
# From repo root — stop Postgres (data persists in the named volume)
docker compose down

# Remove Postgres data for a fresh-clone test
docker compose down -v
```

## Environment variables

See `.env.example` at the repo root:

| Variable | Purpose |
|---|---|
| `BOT_TOKEN` | Telegram bot token |
| `DATABASE_URL` | SQLAlchemy async URL (`postgresql+asyncpg://…`) |
| `POSTGRES_USER` | Postgres user (used by Docker Compose) |
| `POSTGRES_PASSWORD` | Postgres password (used by Docker Compose) |
| `POSTGRES_DB` | Postgres database name (used by Docker Compose) |

`DATABASE_URL` credentials must match the `POSTGRES_*` values.

## Project layout

```
backend/
  app/
    main.py      # FastAPI app, /health, lifespan DB check
    config.py    # Loads .env from repo root
    db.py        # Async SQLAlchemy engine
  bot/
    main.py      # Aiogram polling bot, /start → pong
  alembic/       # Async migrations (empty baseline for now)
  alembic.ini
```
