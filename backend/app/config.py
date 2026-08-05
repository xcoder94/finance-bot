import os
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_REPO_ROOT / ".env")

DATABASE_URL = os.environ["DATABASE_URL"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
APP_PASS_SECRET = os.environ["APP_PASS_SECRET"]
if not APP_PASS_SECRET:
    raise RuntimeError("APP_PASS_SECRET environment variable is empty")
_raw_mini_app_url = (os.environ.get("MINI_APP_URL") or "").strip()
MINI_APP_URL: str | None = _raw_mini_app_url or None
SUPPORT_CHAT_ID: str | None = os.environ.get("SUPPORT_CHAT_ID") or None

PARSER_PROVIDER = os.environ.get("PARSER_PROVIDER") or None
PARSER_API_KEY = os.environ.get("PARSER_API_KEY") or None
PARSER_MODEL = os.environ.get("PARSER_MODEL") or None

DAILY_MODEL_CALL_LIMIT = int(os.environ.get("DAILY_MODEL_CALL_LIMIT", "50"))
DAILY_UNPARSED_LIMIT = int(os.environ.get("DAILY_UNPARSED_LIMIT", "20"))

RECEIPT_PHOTO_ENABLED = os.environ.get("RECEIPT_PHOTO_ENABLED")

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
