from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.pass_tokens import AppPassError, decode_app_pass
from app.config import APP_PASS_SECRET
from app.db import get_session
from app.models.revoked_app_pass import RevokedAppPass


async def get_app_pass_claims(
    authorization: Annotated[str | None, Header()] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = ...,
) -> dict[str, Any]:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401)
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401)
    try:
        claims = decode_app_pass(token, APP_PASS_SECRET)
    except AppPassError:
        raise HTTPException(status_code=401) from None

    revoked = await session.scalar(
        select(RevokedAppPass.jti).where(RevokedAppPass.jti == claims["jti"])
    )
    if revoked is not None:
        raise HTTPException(status_code=401)
    return claims


AppPassClaimsDep = Annotated[dict[str, Any], Depends(get_app_pass_claims)]
