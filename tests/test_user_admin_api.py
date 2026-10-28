"""用户账户管理：仅超管可创建 / 删除普通账户、重置密码为 abc123"""
from app.schema import ArticleCreate
from app.service import ArticleService


async def _login(client, username: str, password: str):
    return await client.post(
        "/auth/login", json={"username": username, "password": password}
    )


# ---------- 创建普通账户 ----------


async def test_create_account_uses_default_password(client, superadmin_headers):
    """创建普通账户：密码缺省 abc123，返回 is_superuser=False，可直接登录"""
    resp = await client.post(
        "/users/",
        json={"username": "zhangsan", "nickname": "张三"},
        headers=superadmin_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["nickname"] == "张三"
    assert body["is_superuser"] is False
    assert body["slug"]
    assert (await _login(client, "zhangsan", "abc123")).status_code == 200


async def test_create_account_with_custom_password(client, superadmin_headers):
    resp = await client.post(
        "/users/",
        json={"username": "lisi", "nickname": "李四", "password": "secret6"},
        headers=superadmin_headers,
    )
    assert resp.status_code == 201
    assert (await _login(client, "lisi", "secret6")).status_code == 200


async def test_create_account_cannot_be_superuser(client, superadmin_headers):
    """请求体传 is_superuser 会被忽略：该接口只创建普通账户"""
    resp = await client.post(
        "/users/",
        json={"username": "hacker", "nickname": "黑客", "is_superuser": True},
        headers=superadmin_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["is_superuser"] is False


async def test_create_account_duplicate_username(client, default_user, superadmin_headers):
    resp = await client.post(
        "/users/",
        json={"username": "admin", "nickname": "新昵称"},
        headers=superadmin_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "用户名已存在"


async def test_create_account_duplicate_nickname(client, default_user, superadmin_headers):
    resp = await client.post(
        "/users/",
        json={"username": "newuser", "nickname": "管理员"},
        headers=superadmin_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "昵称已存在"


async def test_create_account_short_password_422(client, superadmin_headers):
    resp = await client.post(
        "/users/",
        json={"username": "shorty", "nickname": "短密码", "password": "123"},
        headers=superadmin_headers,
    )
    assert resp.status_code == 422


async def test_create_account_requires_superadmin(client, auth_headers):
    resp = await client.post(
        "/users/", json={"username": "x", "nickname": "X"}, headers=auth_headers
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "仅超级管理员可管理用户账户"


async def test_create_account_requires_auth(client):
    resp = await client.post("/users/", json={"username": "x", "nickname": "X"})
    assert resp.status_code == 401


# ---------- 重置普通账户密码 ----------


async def test_reset_password_to_abc123(
    client, default_user, superadmin_headers
):
    """重置后 detail 告知 abc123，新密码可登录、旧密码失效"""
    resp = await client.post(
        f"/users/{default_user.id}/reset-password", headers=superadmin_headers
    )
    assert resp.status_code == 200
    assert resp.json() == {"detail": "密码已重置为 abc123"}

    assert (await _login(client, "admin", "abc123")).status_code == 200
    assert (await _login(client, "admin", "test123")).status_code == 401


async def test_reset_superadmin_forbidden(client, superadmin, superadmin_headers):
    resp = await client.post(
        f"/users/{superadmin.id}/reset-password", headers=superadmin_headers
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "不能重置超级管理员密码"


async def test_reset_unknown_user_404(client, superadmin_headers):
    resp = await client.post(
        "/users/9999/reset-password", headers=superadmin_headers
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "用户不存在"


async def test_reset_password_requires_superadmin(client, default_user, auth_headers):
    resp = await client.post(
        f"/users/{default_user.id}/reset-password", headers=auth_headers
    )
    assert resp.status_code == 403


async def test_reset_password_requires_auth(client, default_user):
    resp = await client.post(f"/users/{default_user.id}/reset-password")
    assert resp.status_code == 401


# ---------- 删除普通账户 ----------


async def test_delete_account(client, default_user, superadmin_headers):
    """删除后无法登录、用户列表不再出现"""
    resp = await client.delete(f"/users/{default_user.id}", headers=superadmin_headers)
    assert resp.status_code == 204
    assert resp.content == b""

    assert (await _login(client, "admin", "test123")).status_code == 401
    users = {u["id"] for u in (await client.get("/base/")).json()["user"]}
    assert default_user.id not in users


async def test_delete_account_keeps_articles(
    client, session, default_user, superadmin_headers
):
    """删除账户后其文章保留，作者关联变为 null（无数据库外键）"""
    article = await ArticleService(session).create(
        ArticleCreate(title="离职同事的文章"), user_id=default_user.id
    )
    resp = await client.delete(f"/users/{default_user.id}", headers=superadmin_headers)
    assert resp.status_code == 204

    detail = await client.get(f"/articles/{article.slug}")
    assert detail.status_code == 200
    assert detail.json()["user"] is None


async def test_delete_superadmin_forbidden(client, superadmin, superadmin_headers):
    resp = await client.delete(f"/users/{superadmin.id}", headers=superadmin_headers)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "不能删除超级管理员账户"


async def test_delete_unknown_user_404(client, superadmin_headers):
    resp = await client.delete("/users/9999", headers=superadmin_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "用户不存在"


async def test_delete_requires_superadmin(client, default_user, auth_headers):
    resp = await client.delete(f"/users/{default_user.id}", headers=auth_headers)
    assert resp.status_code == 403


async def test_delete_requires_auth(client, default_user):
    resp = await client.delete(f"/users/{default_user.id}")
    assert resp.status_code == 401
