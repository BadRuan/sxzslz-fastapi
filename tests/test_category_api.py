"""分类 API 层测试：补齐此前仅有 dao/service 测试的盲区。

覆盖：写操作权限（401/403 文案）、sort 排序、三级分类拒绝、
删一级级联清理、batch-category 非法整批不生效。
"""


async def test_category_write_requires_superuser(client, auth_headers, superadmin_headers):
    # 匿名 → 401
    resp = await client.post("/categories/", json={"name": "新闻"})
    assert resp.status_code == 401

    # 普通用户 → 403（文案统一）
    resp = await client.post("/categories/", json={"name": "新闻"}, headers=auth_headers)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "仅超级管理员可管理文章分类"

    resp = await client.patch("/categories/1", json={"name": "改名"}, headers=auth_headers)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "仅超级管理员可管理文章分类"

    resp = await client.delete("/categories/1", headers=auth_headers)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "仅超级管理员可管理文章分类"

    # 分类 GET 保持公开
    resp = await client.get("/categories/")
    assert resp.status_code == 200


async def test_category_sort_order(client, superadmin_headers):
    # 先建 sort=2 再建 sort=1，PATCH 调序后按 sort,id 升序返回
    resp = await client.post(
        "/categories/", json={"name": "后建", "sort": 2}, headers=superadmin_headers
    )
    assert resp.status_code == 201
    cat_b = resp.json()
    resp = await client.post(
        "/categories/", json={"name": "先建", "sort": 1}, headers=superadmin_headers
    )
    cat_a = resp.json()

    resp = await client.get("/categories/")
    names = [c["name"] for c in resp.json()]
    assert names == ["先建", "后建"]

    # PATCH 把「后建」调到最前
    resp = await client.patch(
        f"/categories/{cat_b['id']}", json={"sort": 0}, headers=superadmin_headers
    )
    assert resp.status_code == 200
    resp = await client.get("/categories/")
    names = [c["name"] for c in resp.json()]
    assert names == ["后建", "先建"]


async def test_category_rejects_third_level(client, superadmin_headers):
    resp = await client.post(
        "/categories/", json={"name": "一级"}, headers=superadmin_headers
    )
    parent = resp.json()
    resp = await client.post(
        "/categories/",
        json={"name": "二级", "parent_id": parent["id"]},
        headers=superadmin_headers,
    )
    assert resp.status_code == 201
    child = resp.json()

    # parent 指向二级 → 400
    resp = await client.post(
        "/categories/",
        json={"name": "三级", "parent_id": child["id"]},
        headers=superadmin_headers,
    )
    assert resp.status_code == 400
    assert "三级" in resp.json()["detail"]


async def test_delete_parent_cascades_and_clears_article_category(
    client, session, superadmin_headers
):
    # 建一级 + 二级，文章挂到二级
    resp = await client.post(
        "/categories/", json={"name": "父"}, headers=superadmin_headers
    )
    parent = resp.json()
    resp = await client.post(
        "/categories/", json={"name": "子", "parent_id": parent["id"]}, headers=superadmin_headers
    )
    child = resp.json()
    resp = await client.post(
        "/articles/",
        json={"title": "挂在子分类", "category_ids": [child["id"]]},
        headers=superadmin_headers,
    )
    assert resp.status_code == 201
    slug = resp.json()["slug"]

    # 删一级分类 → 204
    resp = await client.delete(f"/categories/{parent['id']}", headers=superadmin_headers)
    assert resp.status_code == 204

    # 子分类级联删除
    resp = await client.get("/categories/")
    ids = {c["id"] for c in resp.json()}
    assert parent["id"] not in ids
    assert child["id"] not in ids

    # 文章本身不删
    resp = await client.get(f"/articles/{slug}")
    assert resp.status_code == 200

    # article_category 关联被清理：按旧分类过滤应为空
    resp = await client.get("/articles/", params={"category_id": child["id"]})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_batch_category_invalid_slug_rejects_whole_batch(
    client, superadmin_headers
):
    # 一篇文章 + 一个二级分类
    resp = await client.post(
        "/articles/", json={"title": "批量目标"}, headers=superadmin_headers
    )
    slug = resp.json()["slug"]
    resp = await client.post(
        "/categories/", json={"name": "批量分类"}, headers=superadmin_headers
    )
    cat_id = resp.json()["id"]

    # 合法 slug 混一个非法 slug → 整批 400
    resp = await client.post(
        "/articles/batch-category",
        json={"slugs": [slug, "does-not-exist"], "category_id": cat_id, "mode": "add"},
        headers=superadmin_headers,
    )
    assert resp.status_code == 400

    # 整批不生效：合法那篇也没有挂上分类
    resp = await client.get("/articles/", params={"category_id": cat_id})
    assert resp.json()["total"] == 0
