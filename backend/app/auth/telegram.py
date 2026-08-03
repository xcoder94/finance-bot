import hashlib
import hmac
import json
import time
from operator import itemgetter
from typing import Annotated
from urllib.parse import parse_qsl

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

from app.config import BOT_TOKEN

AUTH_MAX_AGE_SECONDS = 3600
PASS_ISSUE_MAX_AGE_SECONDS = 86_400


class TelegramUser(BaseModel):
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None
    is_premium: bool | None = None
    is_bot: bool | None = None
    allows_write_to_pm: bool | None = None
    photo_url: str | None = None


class InitDataValidationError(Exception):
    """Raised when initData fails signature, freshness, or parsing checks."""


def _compute_init_data_hash(data_check_string: str, bot_token: str) -> str:
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode(),
        digestmod=hashlib.sha256,
    ).digest()
    return hmac.new(
        key=secret_key,
        msg=data_check_string.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()


def sign_init_data(fields: dict[str, str], bot_token: str) -> str:
    data_check_string = "\n".join(
        f"{key}={value}"
        for key, value in sorted(fields.items(), key=itemgetter(0))
    )
    init_hash = _compute_init_data_hash(data_check_string, bot_token)
    query = "&".join(f"{key}={value}" for key, value in fields.items())
    return f"{query}&hash={init_hash}"


def _verify_signature(init_data: str, bot_token: str) -> bool:
    try:
        parsed_data = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return False

    received_hash = parsed_data.pop("hash", None)
    if not received_hash:
        return False

    data_check_string = "\n".join(
        f"{key}={value}"
        for key, value in sorted(parsed_data.items(), key=itemgetter(0))
    )
    computed_hash = _compute_init_data_hash(data_check_string, bot_token)
    return hmac.compare_digest(computed_hash, received_hash)


def _parse_user(init_data: str) -> TelegramUser:
    parsed_data = dict(parse_qsl(init_data))
    user_raw = parsed_data.get("user")
    if not user_raw:
        raise InitDataValidationError

    try:
        user_payload = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise InitDataValidationError from exc

    if not isinstance(user_payload, dict):
        raise InitDataValidationError

    return TelegramUser.model_validate(user_payload)


def validate_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int | None = AUTH_MAX_AGE_SECONDS,
    now: int | None = None,
) -> TelegramUser:
    if not init_data or not init_data.strip():
        raise InitDataValidationError

    if not _verify_signature(init_data, bot_token):
        raise InitDataValidationError

    parsed_data = dict(parse_qsl(init_data))
    auth_date_raw = parsed_data.get("auth_date")
    if auth_date_raw is None:
        raise InitDataValidationError

    try:
        auth_date = int(auth_date_raw)
    except ValueError as exc:
        raise InitDataValidationError from exc

    if max_age_seconds is not None:
        current_time = int(time.time()) if now is None else now
        if current_time - auth_date > max_age_seconds:
            raise InitDataValidationError

    return _parse_user(init_data)


def get_telegram_user(
    authorization: Annotated[str | None, Header()] = None,
) -> TelegramUser:
    if authorization is None or not authorization.startswith("tma "):
        raise HTTPException(status_code=401)

    init_data = authorization.removeprefix("tma ")
    if not init_data:
        raise HTTPException(status_code=401)

    try:
        return validate_init_data(init_data, BOT_TOKEN)
    except InitDataValidationError:
        raise HTTPException(status_code=401) from None


TelegramUserDep = Annotated[TelegramUser, Depends(get_telegram_user)]
