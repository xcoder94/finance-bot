from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_MAX_BYTES = 5_000_000
_BACKUP_COUNT = 5
_CONFIGURED = False


class _StripQueryFilter(logging.Filter):
    """uvicorn's access line is '%s - "%s %s HTTP/%s" %d' with the path INCLUDING the query string;
    admin searches carry phones/names there, so only the path part is kept."""

    _strips_query = True

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str) and "?" in args[2]:
            record.args = (*args[:2], args[2].split("?", 1)[0], *args[3:])
        return True


def install_access_log_filter() -> None:
    logger = logging.getLogger("uvicorn.access")
    if not any(getattr(f, "_strips_query", False) for f in logger.filters):
        logger.addFilter(_StripQueryFilter())


def setup_logging() -> None:
    global _CONFIGURED
    install_access_log_filter()
    if _CONFIGURED:
        return

    from app.config import LOG_FILE_PATH

    log_path = Path(LOG_FILE_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    formatter = logging.Formatter(_LOG_FORMAT)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    root.addHandler(console)
    root.addHandler(file_handler)

    _CONFIGURED = True
