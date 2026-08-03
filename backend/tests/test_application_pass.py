import json
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import ExitStack, asynccontextmanager
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.pass_tokens import (
    PASS_LIFETIME_SECONDS,
    AppPassError,
    decode_app_pass,
    issue_app_pass,
)
from app.auth.telegram import PASS_ISSUE_MAX_AGE_SECONDS
from app.db import get_session
from app.main import app
from app.models.family_budget import FamilyBudget
from app.models.revoked_app_pass import RevokedAppPass
from app.models.user import User
from tests.test_telegram_auth import (
    BOT_TOKEN,
    _AsyncSessionFactoryOverride,
    _db_available,
    _random_telegram_id,
    _reset_engine,
    build_fresh_init_data,
    rollback_session,
    sign_init_data,
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


def _build_init_data_for_telegram_id(
    telegram_id: int,
    *,
    auth_date: int | None = None,
) -> str:
    user_json = json.dumps(
        {
            "id": telegram_id,
            "first_name": "Vladislav",
            "last_name": "Kibenko",
            "username": "vdkfrost",
            "language_code": "ru",
            "is_premium": True,
        },
        separators=(",", ":"),
    )
    fields = {
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": user_json,
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
    }
    return sign_init_data(fields, BOT_TOKEN)


@asynccontextmanager
async def _patched_api_client(
    session=None,
) -> AsyncIterator[AsyncClient]:
    session_factory = (
        _AsyncSessionFactoryOverride(session) if session is not None else None
    )

    async def override_get_session() -> AsyncIterator:
        yield session

    if session is not None:
        app.dependency_overrides[get_session] = override_get_session

    with ExitStack() as stack:
        stack.enter_context(patch("app.main.verify_postgres_connection", new=AsyncMock()))
        stack.enter_context(patch("app.api.v1.auth.BOT_TOKEN", BOT_TOKEN))
        stack.enter_context(patch("app.api.v1.auth.APP_PASS_SECRET", SECRET))
        stack.enter_context(patch("app.auth.deps.APP_PASS_SECRET", SECRET))
        if session_factory is not None:
            stack.enter_context(
                patch("app.api.v1.auth.async_session_factory", session_factory)
            )
            stack.enter_context(
                patch("app.api.v1.me.async_session_factory", session_factory)
            )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            try:
                yield client
            finally:
                app.dependency_overrides.clear()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL is not reachable on 127.0.0.1:5432")
@pytest.mark.anyio
async def test_application_pass_allows_api_when_init_data_is_stale() -> None:
    """Phase 0 gate: Bearer pass works; raw tma is rejected on /me."""
    async with rollback_session() as session:
        telegram_id = _random_telegram_id()
        budget = FamilyBudget(invite_token=f"test-{uuid.uuid4()}")
        session.add(budget)
        await session.flush()
        db_user = User(
            telegram_id=telegram_id,
            family_budget_id=budget.id,
            role="owner",
            first_name="AppFirst",
            username="appuser",
            language="uz",
        )
        session.add(db_user)
        await session.flush()

        init_data = _build_init_data_for_telegram_id(telegram_id)
        async with _patched_api_client(session) as client:
            issue_response = await client.post(
                "/api/v1/auth/pass",
                headers={"Authorization": f"tma {init_data}"},
            )
            assert issue_response.status_code == 200
            token = issue_response.json()["access_token"]

            me_bearer = await client.get(
                "/api/v1/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert me_bearer.status_code == 200
            assert me_bearer.json() == {
                "id": str(db_user.id),
                "telegram_id": telegram_id,
                "family_budget_id": str(budget.id),
                "role": "owner",
                "first_name": "AppFirst",
                "username": "appuser",
                "language": "uz",
                "budget_name": "Семейный бюджет",
                "member_count": 1,
            }

            me_tma = await client.get(
                "/api/v1/me",
                headers={"Authorization": f"tma {init_data}"},
            )
            assert me_tma.status_code == 401

            claims = decode_app_pass(token, SECRET)
            session.add(RevokedAppPass(jti=claims["jti"]))
            await session.flush()

            me_revoked = await client.get(
                "/api/v1/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert me_revoked.status_code == 401

    await _reset_engine()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL is not reachable on 127.0.0.1:5432")
@pytest.mark.anyio
async def test_issue_pass_rejects_auth_date_older_than_24h() -> None:
    stale_auth_date = int(time.time()) - PASS_ISSUE_MAX_AGE_SECONDS - 1
    init_data = build_fresh_init_data(auth_date=stale_auth_date)
    async with _patched_api_client() as client:
        response = await client.post(
            "/api/v1/auth/pass",
            headers={"Authorization": f"tma {init_data}"},
        )
    assert response.status_code == 401


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL is not reachable on 127.0.0.1:5432")
@pytest.mark.anyio
async def test_issue_pass_accepts_fresh_init_data() -> None:
    init_data = build_fresh_init_data()
    async with _patched_api_client() as client:
        response = await client.post(
            "/api/v1/auth/pass",
            headers={"Authorization": f"tma {init_data}"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == PASS_LIFETIME_SECONDS
    assert body["access_token"]
    claims = decode_app_pass(body["access_token"], SECRET)
    assert claims["sub"] == "279058397"
