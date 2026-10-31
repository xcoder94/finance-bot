"""fix1 B4: the uvicorn access log never carries the query string (admin searches hold phones)."""

import logging

from app.logging_setup import install_access_log_filter


def _record(path: str) -> logging.LogRecord:
    return logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 1,
        '%s - "%s %s HTTP/%s" %d', ("1.2.3.4:5", "GET", path, "1.1", 200), None,
    )


def test_query_string_is_stripped_from_access_log() -> None:
    install_access_log_filter()
    logger = logging.getLogger("uvicorn.access")
    rec = _record("/api/v1/admin/users?q=%2B998901234567&limit=5")
    assert logger.filter(rec)
    msg = rec.getMessage()
    assert msg == '1.2.3.4:5 - "GET /api/v1/admin/users HTTP/1.1" 200'
    assert "998901234567" not in msg and "?" not in msg


def test_path_without_query_untouched_and_install_is_idempotent() -> None:
    install_access_log_filter()
    install_access_log_filter()
    logger = logging.getLogger("uvicorn.access")
    assert len([f for f in logger.filters if getattr(f, "_strips_query", False)]) == 1
    rec = _record("/health")
    logger.filter(rec)
    assert rec.getMessage() == '1.2.3.4:5 - "GET /health HTTP/1.1" 200'


def test_app_main_installs_filter() -> None:
    import app.main  # noqa: F401

    assert any(getattr(f, "_strips_query", False) for f in logging.getLogger("uvicorn.access").filters)
