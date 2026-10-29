"""文章列表 sort 参数：id / create_at 倒序均可工作；非法 sort 返回 422"""
from datetime import datetime, timedelta, timezone

from app.schema import ArticleCreate
from app.service import ArticleService


async def test_list_sort_default_is_id_desc(client, session, default_user, auth_headers):
    """默认 sort=id（倒序）：最新创建的文章 id 最大排在前面"""
    old = await ArticleService(session).create(
        ArticleCreate(title="旧文章", user_id=default_user.id), user_id=default_user.id
    )
    new = await ArticleService(session).create(
        ArticleCreate(title="新文章", user_id=default_user.id), user_id=default_user.id
    )
    resp = (await client.get("/articles/?sort=id", headers=auth_headers)).json()
    ids = [item["id"] for item in resp["data"]]
    assert ids == sorted(ids, reverse=True)
    assert resp["data"][0]["slug"] == new.slug
    assert resp["data"][-1]["slug"] == old.slug


async def test_list_sort_create_at_desc(client, session, default_user, auth_headers):
    """sort=create_at（倒序）：按发布时间倒序，不报错，结果数正确"""
    now = datetime.now(timezone.utc)
    old_article = await ArticleService(session).create(
        ArticleCreate(
            title="较早文章",
            create_at=now - timedelta(hours=2),
            user_id=default_user.id,
        ),
        user_id=default_user.id,
    )
    new_article = await ArticleService(session).create(
        ArticleCreate(title="较新文章", create_at=now, user_id=default_user.id),
        user_id=default_user.id,
    )
    resp = (await client.get("/articles/?sort=create_at", headers=auth_headers)).json()
    slugs = [item["slug"] for item in resp["data"]]
    assert new_article.slug in slugs
    assert old_article.slug in slugs


async def test_list_sort_invalid_returns_422(client):
    """非法 sort 值 → 422"""
    resp = await client.get("/articles/?sort=invalid")
    assert resp.status_code == 422


async def test_list_sort_with_category_filter(client, session):
    """sort 与 category_id 过滤可共存，不报错"""
    resp = await client.get("/articles/?sort=create_at&category_id=1")
    assert resp.status_code == 200
    assert "data" in resp.json()


async def test_list_sort_with_user_scope_normal_user(
    client, session, default_user, auth_headers
):
    """普通用户带 token：sort 参数透传，仍收敛到本用户文章"""
    article = await ArticleService(session).create(
        ArticleCreate(title="我的文章", user_id=default_user.id),
        user_id=default_user.id,
    )
    resp = (await client.get("/articles/?sort=create_at", headers=auth_headers)).json()
    assert resp["total"] == 1
    assert resp["data"][0]["slug"] == article.slug


async def test_trash_list_sort(client, session, default_user, auth_headers):
    """回收站列表 sort 同样生效：id 倒序、create_at 倒序"""
    a = await ArticleService(session).create(
        ArticleCreate(title="待删旧", user_id=default_user.id), user_id=default_user.id
    )
    b = await ArticleService(session).create(
        ArticleCreate(title="待删新", user_id=default_user.id), user_id=default_user.id
    )
    await ArticleService(session).delete(a.slug)
    await ArticleService(session).delete(b.slug)

    trash = (
        await client.get("/articles/?is_deleted=true&sort=id", headers=auth_headers)
    ).json()
    trash_ids = [item["id"] for item in trash["data"]]
    assert trash_ids == sorted(trash_ids, reverse=True)

    trash2 = (
        await client.get("/articles/?is_deleted=true&sort=create_at", headers=auth_headers)
    ).json()
    assert len(trash2["data"]) == 2
