import time
import uuid
from typing import Any

import jwt

from app.config import APP_PASS_LIFETIME_SECONDS

PASS_LIFETIME_SECONDS = APP_PASS_LIFETIME_SECONDS


class AppPassError(Exception):
    """Raised when an application pass cannot be issued or verified."""


def issue_app_pass(
    *,
    telegram_id: int,
    user_id: uuid.UUID | None,
    secret: str,
    now: int | None = None,
) -> tuple[str, str, int]:
    issued_at = int(time.time()) if now is None else now
    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": str(telegram_id),
        "iat": issued_at,
        "exp": issued_at + PASS_LIFETIME_SECONDS,
        "jti": jti,
    }
    if user_id is not None:
        payload["uid"] = str(user_id)
    token = jwt.encode(payload, secret, algorithm="HS256")
    return token, jti, PASS_LIFETIME_SECONDS


def decode_app_pass(
    token: str,
    secret: str,
    *,
    now: int | None = None,
) -> dict[str, Any]:
    options: dict[str, Any] = {"require": ["sub", "iat", "exp", "jti"]}
    if now is not None:
        options["verify_exp"] = False
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options=options,
            leeway=0,
        )
    except jwt.PyJWTError as exc:
        raise AppPassError from exc
    if now is not None and int(claims["exp"]) < now:
        raise AppPassError
    return claims
