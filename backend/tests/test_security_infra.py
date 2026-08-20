import time
import uuid

from fastapi import Request

from app.auth.pass_tokens import PASS_LIFETIME_SECONDS, decode_app_pass, issue_app_pass, AppPassError
from app.config import APP_PASS_SECRET, asyncpg_dsn, redact_dsn
from app.main import rate_limit_key, verify_postgres_connection
import pytest


# ---------------------------------------------------------------------------
# Task 1 — password never reaches a log or an exception message
# ---------------------------------------------------------------------------


def test_redact_dsn_hides_password_keeps_host_port_db() -> None:
    dsn = "postgresql://myuser:supersecretpw@dbhost:5432/mydb"
    safe = redact_dsn(dsn)
    assert "supersecretpw" not in safe
    assert "dbhost" in safe
    assert "5432" in safe
    assert "mydb" in safe


def test_verify_postgres_connection_error_does_not_leak_password(monkeypatch) -> None:
    import asyncio

    secret_password = "supersecretpw"
    bad_dsn = f"postgresql://myuser:{secret_password}@127.0.0.1:1/mydb"
    monkeypatch.setattr("app.main.asyncpg_dsn", lambda: bad_dsn)
    with pytest.raises(RuntimeError) as excinfo:
        asyncio.run(verify_postgres_connection())
    message = str(excinfo.value)
    assert secret_password not in message
    assert "127.0.0.1" in message
    assert "mydb" in message


# ---------------------------------------------------------------------------
# Task 2 — rate limiter key function
# ---------------------------------------------------------------------------


def _make_request(headers: dict[str, str], client_host: str = "10.0.0.1") -> Request:
    raw_headers = [
        (k.lower().encode(), v.encode()) for k, v in headers.items()
    ]
    scope = {
        "type": "http",
        "headers": raw_headers,
        "client": (client_host, 12345),
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "server": ("test", 80),
        "scheme": "http",
    }
    return Request(scope)


def test_rate_limit_key_uses_sub_claim_for_valid_pass() -> None:
    token, _, _ = issue_app_pass(telegram_id=111, user_id=None, secret=APP_PASS_SECRET)
    request = _make_request({"Authorization": f"Bearer {token}"})
    key = rate_limit_key(request)
    assert key == "user:111"


def test_rate_limit_key_differs_for_different_users() -> None:
    token_a, _, _ = issue_app_pass(telegram_id=111, user_id=None, secret=APP_PASS_SECRET)
    token_b, _, _ = issue_app_pass(telegram_id=222, user_id=None, secret=APP_PASS_SECRET)
    key_a = rate_limit_key(_make_request({"Authorization": f"Bearer {token_a}"}))
    key_b = rate_limit_key(_make_request({"Authorization": f"Bearer {token_b}"}))
    assert key_a != key_b


def test_rate_limit_key_falls_back_to_remote_address_on_garbage_token() -> None:
    request = _make_request({"Authorization": "Bearer not-a-real-token"}, client_host="1.2.3.4")
    key = rate_limit_key(request)
    assert key == "1.2.3.4"


def test_rate_limit_key_falls_back_to_remote_address_on_expired_token() -> None:
    now = int(time.time())
    token, _, _ = issue_app_pass(
        telegram_id=111, user_id=None, secret=APP_PASS_SECRET, now=now - 10 * 24 * 60 * 60
    )
    request = _make_request({"Authorization": f"Bearer {token}"}, client_host="1.2.3.5")
    key = rate_limit_key(request)
    assert key == "1.2.3.5"


def test_rate_limit_key_falls_back_to_remote_address_with_no_token() -> None:
    request = _make_request({}, client_host="1.2.3.6")
    key = rate_limit_key(request)
    assert key == "1.2.3.6"


# ---------------------------------------------------------------------------
# Task 3 — pass token lifetime
# ---------------------------------------------------------------------------


def test_default_pass_lifetime_is_seven_days() -> None:
    assert PASS_LIFETIME_SECONDS == 7 * 24 * 60 * 60


def test_pass_lifetime_env_override(monkeypatch) -> None:
    monkeypatch.setenv("APP_PASS_LIFETIME_SECONDS", "3600")
    import importlib
    import app.config as config_module

    importlib.reload(config_module)
    try:
        assert config_module.APP_PASS_LIFETIME_SECONDS == 3600
    finally:
        monkeypatch.delenv("APP_PASS_LIFETIME_SECONDS", raising=False)
        importlib.reload(config_module)


def test_expired_pass_token_rejected() -> None:
    now = int(time.time())
    token, _, _ = issue_app_pass(
        telegram_id=999, user_id=None, secret=APP_PASS_SECRET, now=now - PASS_LIFETIME_SECONDS - 1
    )
    with pytest.raises(AppPassError):
        decode_app_pass(token, APP_PASS_SECRET, now=now)


def test_limiter_is_actually_wired_to_the_identity_key_func():
    """The key function must be the one the Limiter uses, not merely exist.

    Reverting `key_func=` at the Limiter construction leaves every unit test
    of `rate_limit_key` green while the running app is back to one shared
    bucket for all users, so assert the wiring itself.
    """
    from app.main import limiter, rate_limit_key

    assert limiter._key_func is rate_limit_key


def test_redact_dsn_does_not_echo_a_non_url_connection_string():
    """asyncpg also accepts libpq keyword form, which urlsplit does not reject.

    Without an explicit scheme/netloc check the whole string — password
    included — is returned unchanged.
    """
    from app.config import redact_dsn

    libpq = "host=db.host port=5432 user=usr password=hunter2 dbname=chontakbot"
    assert "hunter2" not in redact_dsn(libpq)
    assert redact_dsn("garbage-hunter2") == "<redacted>"


def test_pass_lifetime_rejects_non_positive_and_garbage_values(monkeypatch):
    """A zero/negative lifetime issues already-expired passes and locks
    every user out of the mini app with no visible cause."""
    import importlib

    import app.config as config_mod

    for bad in ("0", "-1", "abc"):
        monkeypatch.setenv("APP_PASS_LIFETIME_SECONDS", bad)
        with pytest.raises(RuntimeError):
            importlib.reload(config_mod)

    monkeypatch.delenv("APP_PASS_LIFETIME_SECONDS", raising=False)
    importlib.reload(config_mod)
    assert config_mod.APP_PASS_LIFETIME_SECONDS == 7 * 24 * 60 * 60
