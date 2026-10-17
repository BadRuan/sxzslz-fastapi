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
