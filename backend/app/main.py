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
from app.config import CORS_ALLOWED_ORIGINS, RATE_LIMIT_DEFAULT, asyncpg_dsn
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
            f"{DB_CONNECT_TIMEOUT_SECONDS}s ({dsn!r}). "
            "Is the database running? Try: docker compose up -d"
        )
        raise RuntimeError(msg) from exc
    except Exception as exc:
        msg = (
            f"Failed to connect to PostgreSQL ({dsn!r}): {exc}. "
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


limiter = Limiter(key_func=get_remote_address, default_limits=[RATE_LIMIT_DEFAULT])

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
