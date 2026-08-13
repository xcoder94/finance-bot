# Deployment — Docker Compose / Coolify

This document covers `docker-compose.yml` in the repository root: what it
starts, what it needs, and how to run it on Coolify.

For local development without Docker see `backend/README.md`.

---

## 1. What the stack contains

| Service | Image built from | Process | Port | Public |
|---|---|---|---|---|
| `api` | `backend/Dockerfile` | `alembic upgrade head`, then Gunicorn + Uvicorn workers | 5001 | no |
| `bot` | `backend/Dockerfile` (same image) | `python -m bot.main` — Aiogram long polling | — | no |
| `web` | `frontend/Dockerfile` | nginx: serves the built mini app, proxies `/api/` to `api` | 80 | yes |

`api` and `bot` share one image, `chontak-backend:latest`. The image is built
once; the `bot` service only overrides the start command. Building it twice
would produce two identical images.

**PostgreSQL is not part of this stack.** It is an external resource, reached
through `DATABASE_URL`. Nothing in this compose file creates, migrates away or
deletes a database volume.

### Startup order

```
api  → migrations, then /health starts answering
bot  → starts only after api reports healthy
web  → starts after bot
```

Enforced by `depends_on` plus the healthcheck on `api`. If `api` fails to
start, neither `bot` nor `web` is created — the whole deployment fails, and no
half-working version goes live.

### Request path in production

The mini app calls the API with relative URLs (`fetch('/api/v1/wallets')`), so
both must sit on the same origin. Only `web` is exposed publicly; nginx serves
static files and forwards everything under `/api/` to the `api` service over
the internal docker network.

```
Telegram → Coolify proxy → web (nginx) ──┬── static files (mini app)
                                         └── /api/ → api → PostgreSQL
```

---

## 2. Before deploying

- A PostgreSQL resource running in Coolify (or any Postgres reachable from the
  stack's docker network).
- A bot token from [@BotFather](https://t.me/BotFather).
- A domain for the mini app, with TLS. Telegram only opens mini apps over
  `https`.
- Outbound internet access from the containers. `api` calls
  `api.telegram.org` during startup; without it the container will not boot.

---

## 3. Environment variables

Copy `.env.example`, or set the same keys in Coolify's Environment Variables
tab for the resource. Everything the containers read is listed there.

### Required

| Variable | Meaning |
|---|---|
| `DATABASE_URL` | Async SQLAlchemy URL: `postgresql+asyncpg://user:pass@host:5432/db`. The host must resolve inside the stack's network — a service name, never `localhost`. |
| `BOT_TOKEN` | Telegram bot token. |
| `APP_PASS_SECRET` | Signing secret for app passes. Any long random string. Changing it invalidates every pass already issued. |
| `MINI_APP_URL` | Public `https` URL of the mini app — the domain attached to `web`. |

### Optional — API

| Variable | Default | Meaning |
|---|---|---|
| `CORS_ALLOWED_ORIGINS` | empty | Comma-separated origins allowed to call the API. Empty falls back to `MINI_APP_URL` alone. |
| `RATE_LIMIT_DEFAULT` | `120/minute` | Per-IP limit on every route. Over the limit returns `429`. |
| `API_PORT` | `5001` | Port the API listens on inside the container. |
| `WEB_CONCURRENCY` | `4` | Gunicorn worker count. Rule of thumb: `2 × cores + 1`. |
| `LOG_FILE_PATH` | `/app/logs/app.log` | Log file inside the container. Logs also go to stdout, which is what Coolify shows. |

### Optional — bot

| Variable | Default | Meaning |
|---|---|---|
| `SUPPORT_CHAT_ID` | empty | Telegram chat id receiving support messages. Empty disables the relay. |

### Optional — message parsing

| Variable | Default | Meaning |
|---|---|---|
| `PARSER_PROVIDER` | empty | `openai`, `anthropic` or `google`. |
| `PARSER_API_KEY` | empty | While empty, parsing stays inactive and the bot answers with the fallback path. |
| `PARSER_MODEL` | empty | Model name for the chosen provider. |
| `DAILY_MODEL_CALL_LIMIT` | `50` | Per-budget daily cap on model calls. |
| `DAILY_UNPARSED_LIMIT` | `20` | Per-budget daily cap on unparsed messages. |
| `RECEIPT_PHOTO_ENABLED` | empty | `1`, `true`, `yes` or `on` enables receipt photo entry. |

Voice messages and receipt photos require `PARSER_PROVIDER=google`; the other
providers reject those requests.

### Optional — mini app

| Variable | Default | Meaning |
|---|---|---|
| `BACKEND_URL` | `http://api:${API_PORT}` | Where nginx forwards `/api/`. Leave empty while the backend lives in this compose file. No trailing slash. |

---

## 4. Deploying on Coolify

1. **Create the resource.** Project → New Resource → Docker Compose, pointed at
   this git repository. Compose file location: `/docker-compose.yml`.
2. **Set environment variables** from section 3 in the resource's Environment
   Variables tab.
3. **Attach the database.** Take the PostgreSQL resource's internal hostname
   from Coolify and put it in `DATABASE_URL`. Connect the database's network to
   this stack if they are separate resources — see section 7.
4. **Attach the domain** to the `web` service (port 80). Do not expose `api` or
   `bot` publicly; nginx already reaches the API internally.
5. **Set `MINI_APP_URL`** to that same domain.
6. **Deploy.** First deployment builds both images, runs all migrations and
   starts the three services in order.
7. **Register the mini app** in @BotFather with the same URL.

Ports are declared with `expose`, not `ports` — nothing is published on the
host, and Coolify's proxy handles external traffic. This is deliberate; do not
change it to `ports` unless you intend to open the API to the internet.

---

## 5. Updating

Push to the branch Coolify watches, or press Redeploy. Each deployment:

1. rebuilds the images (cached layers are reused);
2. runs `alembic upgrade head` inside the `api` container;
3. restarts the three services in order.

**Migrations are safe to re-run.** Alembic records the current revision in the
`alembic_version` table and applies only revisions missing from it. A
deployment with no new migrations touches nothing:

```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
```

No `Running upgrade` line means nothing was applied. Existing rows are never
rewritten, and no migration in `upgrade()` drops a table or a column.

If a migration fails, PostgreSQL rolls that revision back, `api` never starts,
and `bot` and `web` are not started either. When several new revisions ship at
once and a later one fails, the earlier ones stay applied and the database sits
on an intermediate revision — repair that with a new migration, not by hand.

Run only **one `api` replica**. Multiple replicas would race each other on the
migration step.

---

## 6. Running the stack locally

Requires a reachable PostgreSQL; the compose file does not start one.

```bash
cp .env.example .env          # fill in DATABASE_URL, BOT_TOKEN, APP_PASS_SECRET, MINI_APP_URL
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f api
```

Useful commands:

```bash
# Check the file parses and see every resolved value
docker compose config

# Run migrations by hand, without starting the API
docker compose run --rm --no-deps api alembic upgrade head

# Current database revision
docker compose run --rm --no-deps api alembic current

# Open a shell in the backend image
docker compose run --rm --no-deps api bash

# Stop everything (external PostgreSQL is untouched)
docker compose down
```

`docker compose down -v` removes this stack's volumes. The external database is
not one of them, so its data survives — but do not use the flag against the
PostgreSQL resource itself.

---

## 7. Networking

Containers reach each other by service name on the stack's network: nginx talks
to `http://api:5001`, and both `api` and `bot` talk to the database host named
in `DATABASE_URL`.

If PostgreSQL is a separate Coolify resource, the two are not on the same
network by default. Either connect the database's network to this stack in
Coolify, or use a host that resolves from here. A `DATABASE_URL` pointing at
`localhost` or `127.0.0.1` always fails: inside a container that is the
container itself.

The symptom of an unreachable database is this line in the `api` logs:

```
socket.gaierror: [Errno -3] Temporary failure in name resolution
```

---

## 8. Health and logs

- `api` — `GET /health` → `{"status":"ok"}`, checked every 15s inside the
  container.
- `web` — `GET /healthz` → `ok`.
- `bot` has no healthcheck; long polling exposes no HTTP endpoint. Judge it by
  its logs and by whether it answers in Telegram.

```bash
docker compose logs api
docker compose logs bot
docker compose logs web
```

All three write to stdout, so Coolify's log view shows everything. The file at
`LOG_FILE_PATH` lives inside the container and disappears on redeploy; attach a
volume if you need it kept.

---

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `dependency failed to start: container ...api-1 is unhealthy` | API did not boot; `bot` and `web` were held back on purpose | Read `docker compose logs api` — the real reason is there |
| `TelegramUnauthorizedError: Unauthorized` on `api` startup | Wrong or empty `BOT_TOKEN` | Fix the token; both `api` and `bot` need it |
| `Temporary failure in name resolution` | Database host is not reachable from the stack | Section 7 |
| `502` from the mini app on `/api/...` | `api` is down, or `BACKEND_URL` points at the wrong place | Check `api` first; leave `BACKEND_URL` empty when the backend is in this stack |
| Mini app opens, but the browser blocks API calls with a CORS message | The origin is not on the allowed list | Set `MINI_APP_URL` to the real domain, or list the origins in `CORS_ALLOWED_ORIGINS` |
| Requests fail with `429` | Rate limit | Raise `RATE_LIMIT_DEFAULT` |
| `bot` restarts in a loop on the very first deployment | Tables not created yet | It resolves itself once `api` finishes migrating; if it persists, check `api` |

---

## 10. Known limitations

- The frontend has no `package-lock.json`, so two builds of the same commit can
  resolve different package versions. `npm install` also runs with
  `--legacy-peer-deps`: `@telegram-apps/telegram-ui` declares a React 18 peer
  while the project runs React 19.
- Migrations run in the `api` container only, which is why a single replica is
  required.
- Database backups are configured in Coolify on the PostgreSQL resource, not
  here. Turn them on before the first production deployment.
