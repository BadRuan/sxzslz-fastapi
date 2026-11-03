"""文章列表排序：默认按发布时间（create_at）倒序；id 倒序可显式切换；非法 sort 返回 422"""
from datetime import datetime, timedelta, timezone

from app.schema import ArticleCreate
from app.service import ArticleService


async def _create_article(
    session, user_id: int, create_at: datetime, title: str = "文章"
):
    """统一构造带指定发布时间的文章（超管可指定 create_at 的 service 路径）"""
    return await ArticleService(session).create(
        ArticleCreate(title=title, create_at=create_at, user_id=user_id),
        user_id=user_id,
    )


async def test_list_default_is_create_at_desc(client, session, default_user, auth_headers):
    """默认排序 = create_at 倒序：发布时间最新的排最前，与创建先后无关"""
    now = datetime.now(timezone.utc)
    older = await _create_article(session, default_user.id, now - timedelta(days=2), "较早")
    middle = await _create_article(session, default_user.id, now - timedelta(days=1), "中间")
    newest = await _create_article(session, default_user.id, now, "最新")

    resp = (await client.get("/articles/", headers=auth_headers)).json()
    slugs = [item["slug"] for item in resp["data"]]
    assert slugs == [newest.slug, middle.slug, older.slug]


async def test_list_sort_id_desc(client, session, default_user, auth_headers):
    """显式 sort=id：按发布 id 倒序，与默认的发布时间排序区分开"""
    now = datetime.now(timezone.utc)
    # 先创建的文章发布时间更晚，两种排序结果相反
    first = await _create_article(session, default_user.id, now, "先创建、发布时间晚")
    second = await _create_article(
        session, default_user.id, now - timedelta(days=1), "后创建、发布时间早"
    )

    by_id = (await client.get("/articles/?sort=id", headers=auth_headers)).json()
    assert [item["slug"] for item in by_id["data"]] == [second.slug, first.slug]

    by_default = (await client.get("/articles/", headers=auth_headers)).json()
    assert [item["slug"] for item in by_default["data"]] == [first.slug, second.slug]


async def test_list_create_at_tie_falls_back_to_id_desc(
    client, session, default_user, auth_headers
):
    """create_at 相同时按 id 倒序兜底，保证分页顺序确定"""
    same_time = datetime.now(timezone.utc)
    first = await _create_article(session, default_user.id, same_time, "同一时间先创建")
    second = await _create_article(session, default_user.id, same_time, "同一时间后创建")

    resp = (await client.get("/articles/", headers=auth_headers)).json()
    assert [item["slug"] for item in resp["data"]] == [second.slug, first.slug]


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


async def test_trash_list_default_is_create_at_desc(
    client, session, default_user, auth_headers
):
    """回收站列表同样默认按 create_at 倒序；sort=id 可切换"""
    now = datetime.now(timezone.utc)
    older = await _create_article(session, default_user.id, now - timedelta(days=1), "待删旧")
    newer = await _create_article(session, default_user.id, now, "待删新")
    await ArticleService(session).delete(older.slug)
    await ArticleService(session).delete(newer.slug)

    trash = (
        await client.get("/articles/?is_deleted=true", headers=auth_headers)
    ).json()
    assert [item["slug"] for item in trash["data"]] == [newer.slug, older.slug]

    by_id = (
        await client.get("/articles/?is_deleted=true&sort=id", headers=auth_headers)
    ).json()
    assert [item["slug"] for item in by_id["data"]] == [newer.slug, older.slug]
