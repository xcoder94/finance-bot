from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import select

from app.auth.pass_tokens import issue_app_pass
from app.auth.telegram import (
    PASS_ISSUE_MAX_AGE_SECONDS,
    InitDataValidationError,
    validate_init_data,
)
from app.config import APP_PASS_SECRET, BOT_TOKEN
from app.db import async_session_factory
from app.models.user import User

router = APIRouter(prefix="/api/v1/auth")


@router.post("/pass")
async def create_pass(authorization: str | None = Header(default=None)) -> dict:
    if authorization is None or not authorization.startswith("tma "):
        raise HTTPException(status_code=401)
    init_data = authorization.removeprefix("tma ")
    try:
        tg_user = validate_init_data(
            init_data,
            BOT_TOKEN,
            max_age_seconds=PASS_ISSUE_MAX_AGE_SECONDS,
        )
    except InitDataValidationError:
        raise HTTPException(status_code=401) from None

    async with async_session_factory() as session:
        db_user = await session.scalar(
            select(User).where(User.telegram_id == tg_user.id)
        )
        user_id = None if db_user is None else db_user.id

    token, _jti, expires_in = issue_app_pass(
        telegram_id=tg_user.id,
        user_id=user_id,
        secret=APP_PASS_SECRET,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
    }
