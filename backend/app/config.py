import os
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")

DATABASE_URL = os.environ["DATABASE_URL"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
MINI_APP_URL = os.environ["MINI_APP_URL"]
if not MINI_APP_URL:
    raise RuntimeError("MINI_APP_URL environment variable is empty")


def asyncpg_dsn() -> str:
    """Convert SQLAlchemy async URL to an asyncpg-compatible DSN."""
    url = DATABASE_URL
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url.removeprefix("postgresql+asyncpg://")
    return url
