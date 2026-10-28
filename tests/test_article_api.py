"""文章模块 API 层测试：文章一律以 slug 定位（id 定位与 detail 前缀路由均已移除）"""
from app.schema import ArticleCreate
from app.service import ArticleService


async def _create(session, title="API文章"):
    service = ArticleService(session)
    return await service.create(ArticleCreate(title=title, content="正文"))


async def test_get_article_by_slug(client, session):
    out = await _create(session)
    resp = await client.get(f"/articles/{out.slug}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["slug"] == out.slug
    assert data["content"] == "正文"


async def test_get_unknown_slug_returns_404(client):
    resp = await client.get("/articles/no-such-slug")
    assert resp.status_code == 404


async def test_get_by_numeric_id_removed(client, session):
    """按 id 定位已移除：数字 id 不再解析为文章"""
    out = await _create(session)
    resp = await client.get(f"/articles/{out.id}")
    assert resp.status_code == 404


async def test_detail_prefix_route_removed(client, session):
    """/articles/detail/{slug} 旧路由已移除"""
    out = await _create(session)
    resp = await client.get(f"/articles/detail/{out.slug}")
    assert resp.status_code == 404


async def test_patch_article_by_slug(client, session, auth_headers):
    out = await _create(session, title="旧标题")
    resp = await client.patch(
        f"/articles/{out.slug}", json={"title": "新标题"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "新标题"


async def test_patch_unknown_slug_returns_404(client, auth_headers):
    resp = await client.patch(
        "/articles/no-such-slug", json={"title": "x"}, headers=auth_headers
    )
    assert resp.status_code == 404


async def test_delete_article_by_slug(client, session, auth_headers):
    out = await _create(session)
    resp = await client.delete(f"/articles/{out.slug}", headers=auth_headers)
    assert resp.status_code == 204
    resp2 = await client.get(f"/articles/{out.slug}")
    assert resp2.status_code == 404


async def test_delete_unknown_slug_returns_404(client, auth_headers):
    resp = await client.delete("/articles/no-such-slug", headers=auth_headers)
    assert resp.status_code == 404


async def test_list_filter_by_user_id(client, session, default_user):
    """GET /articles/?user_id= 按作者过滤（后台展示登录账户文章）"""
    await _create(session, title="作者文章")
    resp = await client.get(f"/articles/?user_id={default_user.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["title"] == "作者文章"
    assert body["data"][0]["user"]["id"] == default_user.id

    resp2 = await client.get("/articles/?user_id=999")
    assert resp2.status_code == 200
    assert resp2.json()["total"] == 0


async def test_create_article_owned_by_current_user(client, auth_headers):
    """创建的文章归属当前登录用户（而非固定 DEFAULT_USER_ID）"""
    resp = await client.post(
        "/articles/", json={"title": "我的文章"}, headers=auth_headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["user"]["nickname"] == "管理员"


async def test_create_article_with_explicit_user_id(client, session, superadmin_headers):
    """超管 body 传 user_id 指定发布主体；响应 user.id 与传入一致"""
    from app.model import User

    other = User.create_user(username="author2", nickname="作者二", password="test123")
    session.add(other)
    await session.flush()

    resp = await client.post(
        "/articles/",
        json={"title": "代发文章", "user_id": other.id},
        headers=superadmin_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["user"]["id"] == other.id
    assert data["user"]["nickname"] == "作者二"


async def test_create_article_explicit_user_id_forbidden_for_normal(
    client, session, default_user, auth_headers
):
    """普通用户不能指定他人为发布主体 → 403"""
    from app.model import User

    other = User.create_user(username="author3", nickname="作者三", password="test123")
    session.add(other)
    await session.flush()

    resp = await client.post(
        "/articles/",
        json={"title": "越权代发", "user_id": other.id},
        headers=auth_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "无权指定其他用户发布"


async def test_create_article_user_id_zero_rejected(client, auth_headers):
    """user_id 必须 ≥1，非法值 422"""
    resp = await client.post(
        "/articles/", json={"title": "非法作者", "user_id": 0}, headers=auth_headers
    )
    assert resp.status_code == 422


async def test_like_article_anonymous(client, session):
    """匿名点赞：公开接口，每次 +1，详情同步更新"""
    out = await _create(session, title="点赞文章")
    resp = await client.post(f"/articles/{out.slug}/like")
    assert resp.status_code == 200
    assert resp.json() == {"like_count": 1}

    resp2 = await client.post(f"/articles/{out.slug}/like")
    assert resp2.json() == {"like_count": 2}

    detail = await client.get(f"/articles/{out.slug}")
    assert detail.json()["like_count"] == 2


async def test_like_unknown_article_returns_404(client):
    resp = await client.post("/articles/no-such-slug/like")
    assert resp.status_code == 404


async def test_deleted_article_hidden_until_restored(client, session, auth_headers):
    """软删除 → 前台列表/详情不可见；回收站可见；恢复后重新可见"""
    out = await _create(session, title="待删文章")
    resp = await client.delete(f"/articles/{out.slug}", headers=auth_headers)
    assert resp.status_code == 204

    # 正常列表与详情都不返回已删文章
    normal = await client.get("/articles/")
    assert normal.json()["total"] == 0
    assert (await client.get(f"/articles/{out.slug}")).status_code == 404

    # 回收站只返回已删文章
    trash = await client.get("/articles/?is_deleted=true")
    assert trash.status_code == 200
    body = trash.json()
    assert body["total"] == 1
    assert body["data"][0]["slug"] == out.slug
    assert body["data"][0]["is_deleted"] is True

    # 恢复后回到正常列表
    restored = await client.post(f"/articles/{out.slug}/restore", headers=auth_headers)
    assert restored.status_code == 200
    assert restored.json()["is_deleted"] is False
    assert (await client.get(f"/articles/{out.slug}")).status_code == 200
    assert (await client.get("/articles/")).json()["total"] == 1
    assert (await client.get("/articles/?is_deleted=true")).json()["total"] == 0


async def test_restore_requires_auth_and_valid_slug(client, session, auth_headers):
    """恢复需要登录；未知 slug 返回 404"""
    out = await _create(session)
    assert (
        await client.post(f"/articles/{out.slug}/restore")
    ).status_code == 401
    assert (
        await client.post("/articles/no-such-slug/restore", headers=auth_headers)
    ).status_code == 404


async def test_detail_view_count_increments(client, session):
    """详情访问匿名自增 view_count，响应返回自增后的值"""
    out = await _create(session, title="阅读量文章")
    assert (await client.get(f"/articles/{out.slug}")).json()["view_count"] == 1
    assert (await client.get(f"/articles/{out.slug}")).json()["view_count"] == 2


async def test_deleted_article_detail_does_not_count(client, session, auth_headers):
    """已删文章详情 404 且不消耗阅读量；恢复后继续正常计数"""
    out = await _create(session, title="计数边界")
    await client.delete(f"/articles/{out.slug}", headers=auth_headers)
    assert (await client.get(f"/articles/{out.slug}")).status_code == 404
    restored = await client.post(f"/articles/{out.slug}/restore", headers=auth_headers)
    assert restored.json()["view_count"] == 0
    assert (await client.get(f"/articles/{out.slug}")).json()["view_count"] == 1


async def test_batch_category_add_and_remove(client, session, auth_headers):
    """批量加入 → 按分类可见；批量移出 → 不可见；重复操作幂等"""
    from app.dao import CategoryCrud

    cat_crud = CategoryCrud(session)
    parent = await cat_crud.create(name="批量父", parent_id=0, sort=0)
    cat = await cat_crud.create(name="批量子", parent_id=parent.id, sort=99)
    a = await _create(session, title="批量A")
    b = await _create(session, title="批量B")

    batch = {"slugs": [a.slug, b.slug], "category_id": cat.id, "mode": "add"}
    resp = await client.post("/articles/batch-category", json=batch, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"affected": 2}
    assert (await client.get(f"/articles/?category_id={cat.id}")).json()["total"] == 2

    # 幂等再加：关联不重复
    resp2 = await client.post("/articles/batch-category", json=batch, headers=auth_headers)
    assert resp2.json()["affected"] == 2
    detail = (await client.get(f"/articles/{a.slug}")).json()
    assert [c["id"] for c in detail["categories"]] == [cat.id]

    batch["mode"] = "remove"
    resp3 = await client.post("/articles/batch-category", json=batch, headers=auth_headers)
    assert resp3.json()["affected"] == 2
    assert (await client.get(f"/articles/?category_id={cat.id}")).json()["total"] == 0
    assert (await client.get(f"/articles/{a.slug}")).json()["categories"] == []


async def test_batch_category_errors(client, session, auth_headers):
    """401 未登录；400 一级分类/未知 slug；422 空 slugs 或非法 mode"""
    from app.dao import CategoryCrud

    cat_crud = CategoryCrud(session)
    top = await cat_crud.create(name="错误一级", parent_id=0, sort=0)
    cat = await _level2_for_batch(cat_crud)
    a = await _create(session)
    valid = {"slugs": [a.slug], "category_id": cat.id, "mode": "add"}

    assert (
        await client.post("/articles/batch-category", json=valid)
    ).status_code == 401

    level1 = {**valid, "category_id": top.id}
    assert (
        await client.post("/articles/batch-category", json=level1, headers=auth_headers)
    ).status_code == 400

    unknown = {**valid, "slugs": ["no-such-slug"]}
    assert (
        await client.post("/articles/batch-category", json=unknown, headers=auth_headers)
    ).status_code == 400

    assert (
        await client.post(
            "/articles/batch-category",
            json={**valid, "slugs": []},
            headers=auth_headers,
        )
    ).status_code == 422
    assert (
        await client.post(
            "/articles/batch-category",
            json={**valid, "mode": "replace"},
            headers=auth_headers,
        )
    ).status_code == 422


async def _level2_for_batch(cat_crud):
    parent = await cat_crud.create(name="错误父", parent_id=0, sort=0)
    return await cat_crud.create(name="错误子", parent_id=parent.id, sort=0)


async def test_article_out_has_is_deleted_not_is_hidden(client, session):
    """响应体用 is_deleted 表达可见性，is_hidden 已移除"""
    out = await _create(session)
    data = (await client.get(f"/articles/{out.slug}")).json()
    assert data["is_deleted"] is False
    assert "is_hidden" not in data
