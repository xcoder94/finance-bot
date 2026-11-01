import socket

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.admin_helpers import make_admin, make_user, rand_tid
from tests.db_helpers import db_address
from tests.test_wallets_categories import api_client, auth_headers  # noqa: F401


def _db_available() -> bool:
    try:
        with socket.create_connection(db_address(), timeout=1):
            return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available"),
    pytest.mark.anyio,
]

ADMIN_PATHS = ["/api/v1/admin/overview", "/api/v1/admin/users", "/api/v1/admin/usage"]


@pytest.mark.parametrize("path", ADMIN_PATHS)
async def test_no_token_is_401(api_client, path, monkeypatch) -> None:
    client, _ = api_client
    make_admin(monkeypatch, rand_tid())
    assert (await client.get(path)).status_code == 401


@pytest.mark.parametrize("path", ADMIN_PATHS)
async def test_non_admin_is_404_even_with_valid_user(api_client, path, monkeypatch) -> None:
    client, session = api_client
    make_admin(monkeypatch, rand_tid())  # someone else
    user = await make_user(session)
    resp = await client.get(path, headers=auth_headers(user.telegram_id))
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Not Found"}


@pytest.mark.parametrize("path", ADMIN_PATHS)
async def test_nobody_is_admin_when_env_empty(api_client, path, monkeypatch) -> None:
    client, session = api_client
    make_admin(monkeypatch)  # empty
    user = await make_user(session)
    assert (await client.get(path, headers=auth_headers(user.telegram_id))).status_code == 404


@pytest.mark.parametrize("path", ADMIN_PATHS)
async def test_admin_is_200(api_client, path, monkeypatch) -> None:
    client, session = api_client
    user = await make_user(session)
    make_admin(monkeypatch, user.telegram_id)
    assert (await client.get(path, headers=auth_headers(user.telegram_id))).status_code == 200


async def test_admin_id_comes_from_the_pass_not_from_query(api_client, monkeypatch) -> None:
    client, session = api_client
    admin_tid = rand_tid()
    make_admin(monkeypatch, admin_tid)
    user = await make_user(session)
    resp = await client.get(
        f"/api/v1/admin/overview?telegram_id={admin_tid}",
        headers={**auth_headers(user.telegram_id), "X-Telegram-Id": str(admin_tid)},
    )
    assert resp.status_code == 404


async def test_admin_access_is_logged_without_body(api_client, monkeypatch, caplog) -> None:
    client, session = api_client
    user = await make_user(session, first_name="LeakCheckName", phone="+998901112233")
    make_admin(monkeypatch, user.telegram_id)
    with caplog.at_level("INFO"):
        resp = await client.get(
            "/api/v1/admin/users", headers=auth_headers(user.telegram_id)
        )
    assert resp.status_code == 200
    lines = [r.getMessage() for r in caplog.records if "admin" in r.getMessage().lower()]
    assert any(str(user.telegram_id) in m and "/api/v1/admin/users" in m for m in lines)
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert "LeakCheckName" not in joined and "998901112233" not in joined


async def test_me_is_admin_flag(api_client, monkeypatch) -> None:
    client, session = api_client
    admin = await make_user(session)
    other = await make_user(session)
    make_admin(monkeypatch, admin.telegram_id)
    me_admin = await client.get("/api/v1/me", headers=auth_headers(admin.telegram_id))
    me_other = await client.get("/api/v1/me", headers=auth_headers(other.telegram_id))
    assert me_admin.json()["is_admin"] is True
    assert me_other.json()["is_admin"] is False
    # PATCH /me returns the same shape
    patched = await client.patch(
        "/api/v1/me", headers=auth_headers(admin.telegram_id), json={"language": "uz"}
    )
    assert patched.json()["is_admin"] is True


def test_admin_ids_parsing() -> None:
    from app.config import _parse_admin_ids

    assert _parse_admin_ids(None) == frozenset()
    assert _parse_admin_ids("") == frozenset()
    assert _parse_admin_ids(" 1, 2 ,,3 ") == frozenset({1, 2, 3})
    with pytest.raises(RuntimeError) as exc:
        _parse_admin_ids("12345,abc")
    assert "12345" not in str(exc.value)


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
@pytest.mark.parametrize("path", ADMIN_PATHS + ["/api/v1/admin/nope"])
async def test_non_admin_any_method_is_404_not_405(api_client, path, method, monkeypatch) -> None:
    client, session = api_client
    make_admin(monkeypatch, rand_tid())
    user = await make_user(session)
    for headers in (auth_headers(user.telegram_id), None):
        resp = await getattr(client, method)(path, headers=headers) if headers else await getattr(client, method)(path)
        assert resp.status_code in (404, 401), (method, path, resp.status_code)
        if headers:
            assert resp.status_code == 404 and resp.json() == {"detail": "Not Found"}


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
async def test_admin_write_methods_are_not_exposed(api_client, method, monkeypatch) -> None:
    client, session = api_client
    user = await make_user(session)
    make_admin(monkeypatch, user.telegram_id)
    resp = await getattr(client, method)("/api/v1/admin/overview", headers=auth_headers(user.telegram_id))
    assert resp.status_code == 405


# ---- fix1 B1: the whole /api/v1/admin subtree is invisible to non-admins on any method ----
ALL_METHODS = ["get", "post", "put", "patch", "delete", "head", "options"]
SUBTREE_PATHS = [
    "/api/v1/admin/overview",
    "/api/v1/admin/users",
    "/api/v1/admin/nope",
    "/api/v1/admin",
    "/api/v1/admin/",
    "/api/v1/admin/overview/x",
]


@pytest.mark.parametrize("method", ALL_METHODS)
@pytest.mark.parametrize("path", SUBTREE_PATHS)
async def test_non_admin_subtree_is_404_without_allow(api_client, path, method, monkeypatch) -> None:
    client, session = api_client
    make_admin(monkeypatch, rand_tid())
    user = await make_user(session)
    resp = await getattr(client, method)(path, headers=auth_headers(user.telegram_id))
    assert resp.status_code == 404, (method, path, resp.status_code)
    assert "allow" not in resp.headers
    if method != "head":
        assert resp.json() == {"detail": "Not Found"}


@pytest.mark.parametrize("method", ALL_METHODS)
@pytest.mark.parametrize("path", SUBTREE_PATHS)
async def test_no_token_subtree_is_401_without_allow(api_client, path, method, monkeypatch) -> None:
    client, _ = api_client
    make_admin(monkeypatch, rand_tid())
    resp = await getattr(client, method)(path)
    assert resp.status_code == 401, (method, path, resp.status_code)
    assert "allow" not in resp.headers


@pytest.mark.parametrize("path", ["/api/v1/admin/nope", "/api/v1/admin", "/api/v1/admin/", "/api/v1/admin/overview/x"])
@pytest.mark.parametrize("method", ALL_METHODS)
async def test_admin_unknown_path_is_404(api_client, path, method, monkeypatch) -> None:
    client, session = api_client
    user = await make_user(session)
    make_admin(monkeypatch, user.telegram_id)
    resp = await getattr(client, method)(path, headers=auth_headers(user.telegram_id))
    assert resp.status_code == 404, (method, path, resp.status_code)


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete", "options"])
@pytest.mark.parametrize("path", ADMIN_PATHS)
async def test_admin_known_path_non_get_is_405(api_client, path, method, monkeypatch) -> None:
    client, session = api_client
    user = await make_user(session)
    make_admin(monkeypatch, user.telegram_id)
    resp = await getattr(client, method)(path, headers=auth_headers(user.telegram_id))
    assert resp.status_code == 405
