import asyncio
import logging
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.v1.analytics import router as analytics_router
from app.api.v1.auth import router as auth_router
from app.api.v1.categories import router as categories_router
from app.api.v1.history import router as history_router
from app.api.v1.members import init_bot_username, router as members_router
from app.api.v1.me import router as me_router
from app.api.v1.transactions import router as transactions_router
from app.api.v1.goals import router as goals_router
from app.api.v1.wallets import router as wallets_router
from app.auth.pass_tokens import AppPassError, decode_app_pass
from app.config import APP_PASS_SECRET, CORS_ALLOWED_ORIGINS, RATE_LIMIT_DEFAULT, asyncpg_dsn, redact_dsn
from app.db import dispose_engine
from app.logging_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

DB_CONNECT_TIMEOUT_SECONDS = 5.0


async def verify_postgres_connection() -> None:
    dsn = asyncpg_dsn()
    try:
        conn = await asyncio.wait_for(
            asyncpg.connect(dsn),
            timeout=DB_CONNECT_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        msg = (
            f"PostgreSQL connection timed out after "
            f"{DB_CONNECT_TIMEOUT_SECONDS}s ({redact_dsn(dsn)}). "
            "Is the database running? Try: docker compose up -d"
        )
        raise RuntimeError(msg) from exc
    except Exception as exc:
        msg = (
            f"Failed to connect to PostgreSQL ({redact_dsn(dsn)}): {exc}. "
            "Is the database running? Try: docker compose up -d"
        )
        raise RuntimeError(msg) from exc
    else:
        await conn.close()
        logger.info("PostgreSQL connection verified")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await verify_postgres_connection()
    await init_bot_username()
    yield
    await dispose_engine()


def rate_limit_key(request: Request) -> str:
    """Key the rate limiter on the authenticated user when possible.

    `request.client.host` is the same for every user behind a reverse proxy
    (Traefik) that we do not configure as a trusted proxy, so it must not be
    the sole key. When a request carries a valid signed app pass, key on the
    `sub` claim instead — unspoofable because the signature is verified.
    Never raises and never performs I/O; any failure falls back to the
    remote address.
    """
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        if token:
            try:
                claims = decode_app_pass(token, APP_PASS_SECRET)
            except AppPassError:
                pass
            except Exception:
                pass
            else:
                sub = claims.get("sub")
                if sub:
                    return f"user:{sub}"
    return get_remote_address(request)


limiter = Limiter(key_func=rate_limit_key, default_limits=[RATE_LIMIT_DEFAULT])

app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(me_router)
app.include_router(wallets_router)
app.include_router(goals_router)
app.include_router(categories_router)
app.include_router(history_router)
app.include_router(transactions_router)
app.include_router(analytics_router)
app.include_router(members_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled API exception method=%s path=%s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
