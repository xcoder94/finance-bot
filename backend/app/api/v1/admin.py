"""Admin panel (read-only). Every route sits behind require_admin: non-admin -> 404."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.admin import require_admin
from app.db import get_session
from app.schemas.admin import AdminOverview, AdminUsage, AdminUsersPage
from app.services import admin_stats
from app.services.activity import utcnow

router = APIRouter(prefix="/api/v1/admin", dependencies=[Depends(require_admin)])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/overview")
async def get_overview(session: SessionDep) -> AdminOverview:
    return await admin_stats.build_overview(session, utcnow())


@router.get("/users")
async def get_users(
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=admin_stats.MAX_QUERY_LENGTH)] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AdminUsersPage:
    try:
        return await admin_stats.list_users(session, q=q, cursor=cursor, limit=limit)
    except admin_stats.InvalidCursor:
        raise HTTPException(status_code=422, detail="invalid_cursor") from None


@router.get("/usage")
async def get_usage(
    session: SessionDep, period: Literal["day", "week", "month"] = "day"
) -> AdminUsage:
    return await admin_stats.build_usage(session, utcnow(), period)


_ALL_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
_KNOWN_PATHS = frozenset({f"{router.prefix}/overview", f"{router.prefix}/users", f"{router.prefix}/usage"})


@router.api_route("", methods=_ALL_METHODS, include_in_schema=False)
@router.api_route("/{path:path}", methods=_ALL_METHODS, include_in_schema=False)
async def no_other_routes(request: Request) -> None:
    """Everything under /api/v1/admin that is not a real GET route lands here, behind require_admin:
    no token -> 401, not an admin -> 404 (indistinguishable from an unknown path, no Allow header).
    Only an admin gets this far: a known path with a non-GET method is 405, anything else 404."""
    if request.url.path in _KNOWN_PATHS:
        raise HTTPException(status_code=405, headers={"Allow": "GET"})
    raise HTTPException(status_code=404)
