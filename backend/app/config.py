import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_BACKEND_ROOT / ".env")

DATABASE_URL = os.environ["DATABASE_URL"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
APP_PASS_SECRET = os.environ["APP_PASS_SECRET"]
if not APP_PASS_SECRET:
    raise RuntimeError("APP_PASS_SECRET environment variable is empty")
_raw_mini_app_url = (os.environ.get("MINI_APP_URL") or "").strip()
MINI_APP_URL: str | None = _raw_mini_app_url or None
SUPPORT_CHAT_ID: str | None = os.environ.get("SUPPORT_CHAT_ID") or None

_raw_cors_origins = (os.environ.get("CORS_ALLOWED_ORIGINS") or "").strip()
if _raw_cors_origins:
    CORS_ALLOWED_ORIGINS: list[str] = [
        origin.strip() for origin in _raw_cors_origins.split(",") if origin.strip()
    ]
else:
    CORS_ALLOWED_ORIGINS = [MINI_APP_URL] if MINI_APP_URL else []

RATE_LIMIT_DEFAULT = os.environ.get("RATE_LIMIT_DEFAULT") or "120/minute"

_raw_pass_lifetime = os.environ.get("APP_PASS_LIFETIME_SECONDS") or ""
try:
    APP_PASS_LIFETIME_SECONDS = int(_raw_pass_lifetime or 7 * 24 * 60 * 60)
except ValueError:
    raise RuntimeError(
        "APP_PASS_LIFETIME_SECONDS must be a whole number of seconds, "
        f"got {_raw_pass_lifetime!r}"
    ) from None
if APP_PASS_LIFETIME_SECONDS <= 0:
    # A non-positive lifetime issues passes that are already expired, which
    # locks every user out of the mini app with no visible cause.
    raise RuntimeError(
        "APP_PASS_LIFETIME_SECONDS must be greater than zero, "
        f"got {APP_PASS_LIFETIME_SECONDS}"
    )

PARSER_PROVIDER = os.environ.get("PARSER_PROVIDER") or None
PARSER_API_KEY = os.environ.get("PARSER_API_KEY") or None
PARSER_MODEL = os.environ.get("PARSER_MODEL") or None

def _usd_env(name: str, default: float = 0.0) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise RuntimeError(f"{name} must be a non-negative number (USD)") from None
    if not value >= 0 or value == float("inf"):
        raise RuntimeError(f"{name} must be a non-negative number (USD)")
    return value


# Admin panel: AI cost accounting. Prices are USD per 1M tokens as billed by the provider
# (unset/0 -> that part of the cost is counted as 0, so set them).
AI_PRICE_INPUT_USD_PER_1M = _usd_env("AI_PRICE_INPUT_USD_PER_1M")
AI_PRICE_OUTPUT_USD_PER_1M = _usd_env("AI_PRICE_OUTPUT_USD_PER_1M")
# Optional: input tokens of the audio modality, when the model bills them differently.
AI_PRICE_AUDIO_INPUT_USD_PER_1M = _usd_env("AI_PRICE_AUDIO_INPUT_USD_PER_1M")
# Daily AI spend (Tashkent day) that triggers one Telegram message to every admin. 0/unset = off.
ADMIN_AI_DAILY_COST_ALERT_USD = _usd_env("ADMIN_AI_DAILY_COST_ALERT_USD")


DAILY_MODEL_CALL_LIMIT = int(os.environ.get("DAILY_MODEL_CALL_LIMIT", "50"))
DAILY_UNPARSED_LIMIT = int(os.environ.get("DAILY_UNPARSED_LIMIT", "20"))

RECEIPT_PHOTO_ENABLED = os.environ.get("RECEIPT_PHOTO_ENABLED")


def _parse_admin_ids(raw: str | None) -> frozenset[int]:
    ids: set[int] = set()
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            # Never echo the value: it is an identifier of a privileged account.
            raise RuntimeError(
                "ADMIN_TELEGRAM_IDS must be a comma-separated list of integers"
            ) from None
    return frozenset(ids)


# Empty / unset -> nobody is an admin.
ADMIN_TELEGRAM_IDS: frozenset[int] = _parse_admin_ids(os.environ.get("ADMIN_TELEGRAM_IDS"))

_default_log_file = _BACKEND_ROOT / "logs" / "app.log"
LOG_FILE_PATH = os.environ.get("LOG_FILE_PATH") or str(_default_log_file)


def receipt_photo_enabled() -> bool:
    raw = RECEIPT_PHOTO_ENABLED
    if raw is None:
        return False
    return raw.lower() in {"1", "true", "yes", "on"}


def asyncpg_dsn() -> str:
    """Convert SQLAlchemy async URL to an asyncpg-compatible DSN."""
    url = DATABASE_URL
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url.removeprefix("postgresql+asyncpg://")
    return url


def redact_dsn(dsn: str) -> str:
    """Return a form of a DSN safe to log or raise: no password, no credentials.

    Keeps scheme, host, port and database name (useful for diagnosis).
    Falls back to a fixed marker if the DSN cannot be parsed.
    """
    try:
        parsed = urlsplit(dsn)
        if not parsed.scheme or not parsed.netloc:
            # Not a URL (e.g. libpq keyword form "host=... password=..."):
            # there is no safe way to strip a secret we cannot locate.
            return "<redacted>"
        host = parsed.hostname or "?"
        port = parsed.port
        netloc = f"{host}:{port}" if port is not None else host
        user = parsed.username
        if user:
            netloc = f"{user}:***@{netloc}"
        path = parsed.path or ""
        return urlunsplit((parsed.scheme, netloc, path, "", ""))
    except Exception:
        return "<redacted>"
