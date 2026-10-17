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
