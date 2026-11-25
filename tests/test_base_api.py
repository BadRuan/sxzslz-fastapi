"""GET /base/ 与 GET /base/storage API 测试。"""


async def test_base_info_public(client, session, default_user):
    resp = await client.get("/base/")
    assert resp.status_code == 200
    body = resp.json()
    assert "category" in body and isinstance(body["category"], list)
    assert "user" in body and isinstance(body["user"], list)
    # 用户列表含注册用户
    assert any(u["nickname"] == "管理员" for u in body["user"])
    # 分类树节点字段
    if body["category"]:
        node = body["category"][0]
        for key in ("id", "name", "sort", "children"):
            assert key in node


async def test_base_storage_requires_login(client, auth_headers):
    # 匿名 → 401
    resp = await client.get("/base/storage")
    assert resp.status_code == 401

    # 登录 → 200（只断言容量字段存在，不断言具体数值）
    resp = await client.get("/base/storage", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    for key in ("total", "used", "free", "usage_percent", "uploads_bytes"):
        assert key in body
