# MVP2 vs MVP1 — architectural differences relevant to deploy

- **New Alembic migrations chain** — must run `alembic upgrade head`
  before starting the new code. Latest revision: `v2e3f4a5b6c7`
  (adds `cascade_fallback_log`). Several tables are new since MVP1:
  `support_messages`, `cascade_fallback_log`, plus new columns on
  existing tables (`expense_category.is_protected`,
  `transaction.is_demo`).
- **New required/optional env vars, on top of MVP1's:**
  - `SUPPORT_CHAT_ID` — Telegram chat the support-relay feature sends
    user messages to.
  - `RECEIPT_PHOTO_ENABLED` — feature flag, off unless set to
    `1/true/yes/on`.
  - `LOG_FILE_PATH` — optional, defaults to `backend/logs/app.log`
    (rotating file, 5MB × 5 backups).
  - `PARSER_PROVIDER` / `PARSER_API_KEY` / `PARSER_MODEL` — LLM parser
    config.
  - `DAILY_MODEL_CALL_LIMIT` / `DAILY_UNPARSED_LIMIT` — per-family daily
    quotas.
- **New local error log** (`backend/logs/app.log` by default) — plain
  rotating file on the app server's disk, not shipped anywhere
  external. Make sure the process has write access to that path and
  that log rotation (5×5MB) is acceptable disk usage.
- **Cascade prefilter added in front of the LLM parser** for text
  quick-entry — most messages now get classified locally by keyword
  match before ever calling the model; on a miss it silently falls
  through to the LLM as before, and now also writes one row to
  `cascade_fallback_log` for later review (no behavior change, purely
  additive).
- **Existing families are deliberately NOT migrated** to the new
  category set (PRD §15.5) — they keep their old categories forever;
  the new set only applies to newly-created budgets. Don't run any
  backfill/migration job for this — there isn't supposed to be one.
- **Mini app is a separate frontend** (React/Vite), served at
  `MINI_APP_URL`; the bot only sends deep links to it. Both processes
  (bot + mini app) need to be deployed/reachable independently.
