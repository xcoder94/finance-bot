import uuid

import jwt
import pytest

from app.auth.pass_tokens import (
    PASS_LIFETIME_SECONDS,
    AppPassError,
    decode_app_pass,
    issue_app_pass,
)

SECRET = "test-app-pass-secret-not-for-production"


def test_issue_and_decode_round_trip() -> None:
    uid = uuid.uuid4()
    token, jti, expires_in = issue_app_pass(
        telegram_id=279058397,
        user_id=uid,
        secret=SECRET,
        now=1_700_000_000,
    )
    assert expires_in == PASS_LIFETIME_SECONDS
    assert jti
    claims = decode_app_pass(token, SECRET, now=1_700_000_000)
    assert claims["sub"] == "279058397"
    assert claims["uid"] == str(uid)
    assert claims["jti"] == jti
    assert claims["exp"] == 1_700_000_000 + PASS_LIFETIME_SECONDS


def test_expired_pass_rejected() -> None:
    payload = {
        "sub": "1",
        "iat": 1_700_000_000,
        "exp": 1_700_000_001,
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    with pytest.raises(AppPassError):
        decode_app_pass(token, SECRET)


def test_tampered_pass_rejected() -> None:
    token, _, _ = issue_app_pass(
        telegram_id=1,
        user_id=None,
        secret=SECRET,
        now=1_700_000_000,
    )
    bad = token[:-4] + ("0000" if not token.endswith("0000") else "1111")
    with pytest.raises(AppPassError):
        decode_app_pass(bad, SECRET, now=1_700_000_000)
