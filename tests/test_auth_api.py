"""认证模块 API 层测试"""
from app.auth import create_access_token


async def test_login_success(client, default_user):
    resp = await client.post(
        "/auth/login", json={"username": "admin", "password": "test123"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]


async def test_login_wrong_password(client, default_user):
    resp = await client.post(
        "/auth/login", json={"username": "admin", "password": "wrong"}
    )
    assert resp.status_code == 401


async def test_login_unknown_user(client, default_user):
    resp = await client.post(
        "/auth/login", json={"username": "nobody", "password": "test123"}
    )
    assert resp.status_code == 401


async def test_me_returns_current_user(client, default_user, auth_headers):
    resp = await client.get("/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["nickname"] == "管理员"


async def test_me_without_token_returns_401(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_me_with_invalid_token_returns_401(client):
    resp = await client.get("/auth/me", headers={"Authorization": "Bearer bad.token"})
    assert resp.status_code == 401


async def test_write_without_token_returns_401(client, default_user):
    resp = await client.post("/articles/", json={"title": "x"})
    assert resp.status_code == 401
    resp = await client.post(
        "/categories/", json={"name": "x", "slug": "x"}
    )
    assert resp.status_code == 401


async def test_write_with_expired_token_returns_401(client, default_user):
    import jwt as pyjwt
    from datetime import datetime, timedelta, timezone

    from app.auth import ALGORITHM
    from app.settings import settings

    expired = datetime.now(timezone.utc) - timedelta(minutes=1)
    token = pyjwt.encode(
        {"sub": str(default_user.id), "exp": expired},
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )
    resp = await client.post(
        "/articles/",
        json={"title": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


async def test_reads_are_public(client, default_user):
    resp = await client.get("/articles/")
    assert resp.status_code == 200
    resp = await client.get("/categories/")
    assert resp.status_code == 200


async def test_change_password_success(client, default_user, auth_headers):
    """改密成功：返回 detail，新密码可登录，旧密码失效"""
    resp = await client.put(
        "/auth/password",
        json={"old_password": "test123", "new_password": "newpass456"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"detail": "密码修改成功"}

    old = await client.post(
        "/auth/login", json={"username": "admin", "password": "test123"}
    )
    assert old.status_code == 401
    new = await client.post(
        "/auth/login", json={"username": "admin", "password": "newpass456"}
    )
    assert new.status_code == 200


async def test_change_password_wrong_old_returns_400(client, default_user, auth_headers):
    resp = await client.put(
        "/auth/password",
        json={"old_password": "wrong", "new_password": "newpass456"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "原密码错误"


async def test_change_password_requires_auth(client, default_user):
    resp = await client.put(
        "/auth/password",
        json={"old_password": "test123", "new_password": "newpass456"},
    )
    assert resp.status_code == 401


async def test_change_password_short_new_returns_422(client, default_user, auth_headers):
    resp = await client.put(
        "/auth/password",
        json={"old_password": "test123", "new_password": "123"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


async def test_unexpected_error_returns_json_500():
    """未预期异常经全局 handler 返回 JSON 500（不影响既有路由）。

    Starlette 的 Exception 级 handler 返回响应后会 re-raise 以便服务器记日志，
    因此测试客户端需 raise_app_exceptions=False 才能拿到该响应。
    """
    import httpx

    from main import app

    @app.get("/__test_boom__")
    async def _boom():
        raise RuntimeError("boom")

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/__test_boom__")
        assert resp.status_code == 500
        assert resp.json() == {"detail": "服务器内部错误"}
    finally:
        app.router.routes = [
            r for r in app.router.routes if getattr(r, "path", None) != "/__test_boom__"
        ]
