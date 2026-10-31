"""Where the test database lives: always derived from DATABASE_URL."""

from sqlalchemy.engine import make_url

from app.config import DATABASE_URL


def db_address() -> tuple[str, int]:
    url = make_url(DATABASE_URL)
    return (url.host or "127.0.0.1", url.port or 5432)
