import hashlib
import hmac
import json
import socket
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from operator import itemgetter
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.pass_tokens import issue_app_pass
from app.auth.telegram import (
    AUTH_MAX_AGE_SECONDS,
    InitDataValidationError,
    TelegramUser,
    validate_init_data,
)
from app.db import engine, get_session
from app.main import app
from app.models.family_budget import FamilyBudget
from app.models.user import User

BOT_TOKEN = "5768337691:AAH5YkoiEuPk8-FZa32hStHTqXiLPtAEhx8"
TEST_APP_PASS_SECRET = "test-app-pass-secret-not-for-production"
TEST_INIT_DATA = (
    'query_id=AAHdF6IQAAAAAN0XohDhrOrc&user={"id":279058397,'
    '"first_name":"Vladislav","last_name":"Kibenko","username":"vdkfrost",'
    '"language_code":"ru","is_premium":true}&auth_date=1662771648&'
    "hash=c501b71e775f74ce10e377dea85a7ea24ecd640b223ea86dfe453e0eaed2e2b2"
)
EXPECTED_USER = TelegramUser(
    id=279058397,
    first_name="Vladislav",
    last_name="Kibenko",
    username="vdkfrost",
    language_code="ru",
    is_premium=True,
)


def sign_init_data(fields: dict[str, str], bot_token: str) -> str:
    data_check_string = "\n".join(
        f"{key}={value}"
        for key, value in sorted(fields.items(), key=itemgetter(0))
    )
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode(),
        digestmod=hashlib.sha256,
    ).digest()
    init_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()
    query = "&".join(f"{key}={value}" for key, value in fields.items())
    return f"{query}&hash={init_hash}"


def build_fresh_init_data(
    *,
    bot_token: str = BOT_TOKEN,
    auth_date: int | None = None,
) -> str:
    user_json = json.dumps(
        {
            "id": 279058397,
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
    return sign_init_data(fields, bot_token)


def _db_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            return True
    except OSError:
        return False


async def _reset_engine() -> None:
    await engine.dispose()


@asynccontextmanager
async def rollback_session() -> AsyncIterator[AsyncSession]:
    await _reset_engine()
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await trans.rollback()
            await session.close()


class _AsyncSessionFactoryOverride:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def __call__(self) -> "_AsyncSessionFactoryOverride":
        return self

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *_args: object) -> None:
        pass


def _random_telegram_id() -> int:
    return int(uuid.uuid4().int % 9_000_000_000) + 1_000_000_000


def _bearer_headers(
    telegram_id: int,
    *,
    user_id: uuid.UUID | None = None,
) -> dict[str, str]:
    token, _, _ = issue_app_pass(
        telegram_id=telegram_id,
        user_id=user_id,
        secret=TEST_APP_PASS_SECRET,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client() -> TestClient:
    with patch("app.main.verify_postgres_connection", new=AsyncMock()):
        with TestClient(app) as test_client:
            yield test_client


class TestValidateInitData:
    def test_valid_init_data_returns_parsed_user(self) -> None:
        user = validate_init_data(
            TEST_INIT_DATA,
            BOT_TOKEN,
            max_age_seconds=None,
        )
        assert user == EXPECTED_USER

    def test_tampered_hash_fails(self) -> None:
        tampered = TEST_INIT_DATA.replace(
            "hash=c501b71e775f74ce10e377dea85a7ea24ecd640b223ea86dfe453e0eaed2e2b2",
            "hash=d501b71e775f74ce10e377dea85a7ea24ecd640b223ea86dfe453e0eaed2e2b2",
        )
        with pytest.raises(InitDataValidationError):
            validate_init_data(tampered, BOT_TOKEN, max_age_seconds=None)

    def test_stale_auth_date_fails_even_with_valid_signature(self) -> None:
        with pytest.raises(InitDataValidationError):
            validate_init_data(
                TEST_INIT_DATA,
                BOT_TOKEN,
                now=1662771648 + AUTH_MAX_AGE_SECONDS + 1,
            )

    @pytest.mark.parametrize(
        "init_data",
        [
            "",
            "not-valid-query-string",
            "query_id=abc&auth_date=123",
            "query_id=abc&auth_date=123&hash=deadbeef",
        ],
    )
    def test_malformed_init_data_fails_gracefully(self, init_data: str) -> None:
        with pytest.raises(InitDataValidationError):
            validate_init_data(init_data, BOT_TOKEN, max_age_seconds=None)


class TestMeEndpoint:
    def test_missing_authorization_returns_401(self, client: TestClient) -> None:
        response = client.get("/api/v1/me")
        assert response.status_code == 401

    def test_invalid_authorization_returns_401(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/me",
            headers={"Authorization": "tma garbage-input"},
        )
        assert response.status_code == 401


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.anyio
class TestMeEndpointUserLookup:
    async def test_valid_init_data_without_user_row_returns_404(self) -> None:
        telegram_id = _random_telegram_id()
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
            "auth_date": str(int(time.time())),
        }
        init_data = sign_init_data(fields, BOT_TOKEN)

        async with rollback_session() as session:
            session_factory = _AsyncSessionFactoryOverride(session)

            async def override_get_session() -> AsyncIterator[AsyncSession]:
                yield session

            app.dependency_overrides[get_session] = override_get_session
            try:
                with patch("app.main.verify_postgres_connection", new=AsyncMock()):
                    with patch("app.auth.deps.APP_PASS_SECRET", TEST_APP_PASS_SECRET):
                        with patch(
                            "app.api.v1.me.async_session_factory",
                            session_factory,
                        ):
                            transport = ASGITransport(app=app)
                            async with AsyncClient(
                                transport=transport, base_url="http://test"
                            ) as client:
                                response = await client.get(
                                    "/api/v1/me",
                                    headers=_bearer_headers(telegram_id),
                                )
            finally:
                app.dependency_overrides.clear()

        await _reset_engine()
        assert response.status_code == 404
        assert response.json() == {"detail": "not_onboarded"}

    async def test_valid_init_data_with_deleted_user_returns_403(self) -> None:
        telegram_id = _random_telegram_id()
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
            "auth_date": str(int(time.time())),
        }
        init_data = sign_init_data(fields, BOT_TOKEN)

        async with rollback_session() as session:
            budget = FamilyBudget(invite_token=f"test-{uuid.uuid4()}")
            session.add(budget)
            await session.flush()
            session.add(
                User(
                    telegram_id=telegram_id,
                    family_budget_id=budget.id,
                    role="member",
                    language="ru",
                    is_deleted=True,
                    deleted_at=datetime.now(UTC),
                )
            )
            await session.flush()

            session_factory = _AsyncSessionFactoryOverride(session)

            async def override_get_session() -> AsyncIterator[AsyncSession]:
                yield session

            app.dependency_overrides[get_session] = override_get_session
            try:
                with patch("app.main.verify_postgres_connection", new=AsyncMock()):
                    with patch("app.auth.deps.APP_PASS_SECRET", TEST_APP_PASS_SECRET):
                        with patch(
                            "app.api.v1.me.async_session_factory",
                            session_factory,
                        ):
                            transport = ASGITransport(app=app)
                            async with AsyncClient(
                                transport=transport, base_url="http://test"
                            ) as client:
                                response = await client.get(
                                    "/api/v1/me",
                                    headers=_bearer_headers(telegram_id),
                                )
            finally:
                app.dependency_overrides.clear()

        await _reset_engine()
        assert response.status_code == 403
        assert response.json() == {"detail": "removed_from_family"}

    async def test_valid_init_data_with_active_user_returns_me_response(self) -> None:
        telegram_id = _random_telegram_id()
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
            "auth_date": str(int(time.time())),
        }
        init_data = sign_init_data(fields, BOT_TOKEN)

        async with rollback_session() as session:
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

            session_factory = _AsyncSessionFactoryOverride(session)

            async def override_get_session() -> AsyncIterator[AsyncSession]:
                yield session

            app.dependency_overrides[get_session] = override_get_session
            try:
                with patch("app.main.verify_postgres_connection", new=AsyncMock()):
                    with patch("app.auth.deps.APP_PASS_SECRET", TEST_APP_PASS_SECRET):
                        with patch(
                            "app.api.v1.me.async_session_factory",
                            session_factory,
                        ):
                            transport = ASGITransport(app=app)
                            async with AsyncClient(
                                transport=transport, base_url="http://test"
                            ) as client:
                                response = await client.get(
                                    "/api/v1/me",
                                    headers=_bearer_headers(
                                        telegram_id,
                                        user_id=db_user.id,
                                    ),
                                )
            finally:
                app.dependency_overrides.clear()

        await _reset_engine()
        assert response.status_code == 200
        assert response.json() == {
            "id": str(db_user.id),
            "telegram_id": telegram_id,
            "family_budget_id": str(budget.id),
            "role": "owner",
            "first_name": "AppFirst",
            "username": "appuser",
            "language": "uz",
        }
