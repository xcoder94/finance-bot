"""Admin access: Telegram IDs from env ADMIN_TELEGRAM_IDS, checked on every request."""

import logging

from fastapi import HTTPException, Request

from app import config
from app.auth.deps import AppPassClaimsDep

logger = logging.getLogger(__name__)


def is_admin_telegram_id(telegram_id: int) -> bool:
    return telegram_id in config.ADMIN_TELEGRAM_IDS


async def require_admin(request: Request, claims: AppPassClaimsDep) -> int:
    """The id comes from the verified app pass only. Not an admin -> 404 (as an unknown path);
    no valid pass -> 401 (raised by the claims dependency). Logs id + path, never bodies."""
    telegram_id = int(claims["sub"])
    if not is_admin_telegram_id(telegram_id):
        raise HTTPException(status_code=404)
    logger.info("admin access telegram_id=%s path=%s", telegram_id, request.url.path)
    return telegram_id
