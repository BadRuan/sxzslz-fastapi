"""文章列表排序：匿名默认 create_at 倒序（前台新闻），登录默认 id 倒序（后台管理），sort 可显式切换"""
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


async def _seed_reversed_order(session, user_id: int):
    """id 顺序与 create_at 顺序相反，便于区分两种排序：
    先创建的 newer（id 小、发布时间新），后创建的 older（id 大、发布时间旧）"""
    now = datetime.now(timezone.utc)
    newer = await _create_article(session, user_id, now, "发布时间较新")
    older = await _create_article(session, user_id, now - timedelta(days=2), "发布时间较旧")
    return newer, older


async def test_anonymous_default_is_create_at_desc(client, session, default_user):
    """匿名（前台新闻列表）默认按发布时间倒序：发布时间新的在前"""
    newer, older = await _seed_reversed_order(session, default_user.id)
    resp = (await client.get("/articles/")).json()
    assert [item["slug"] for item in resp["data"]] == [newer.slug, older.slug]


async def test_authenticated_default_is_id_desc(
    client, session, default_user, auth_headers
):
    """登录态（后台管理）默认按发布 id 倒序：后创建的文章在前，与发布时间无关"""
    newer, older = await _seed_reversed_order(session, default_user.id)
    resp = (await client.get("/articles/", headers=auth_headers)).json()
    assert [item["slug"] for item in resp["data"]] == [older.slug, newer.slug]


async def test_superadmin_default_is_id_desc(
    client, session, superadmin, superadmin_headers
):
    """超管后台列表同样默认 id 倒序"""
    newer, older = await _seed_reversed_order(session, superadmin.id)
    resp = (await client.get("/articles/", headers=superadmin_headers)).json()
    assert [item["slug"] for item in resp["data"]] == [older.slug, newer.slug]


async def test_authenticated_select_create_at(
    client, session, default_user, auth_headers
):
    """后台选择按日期排序：显式 sort=create_at → 发布时间倒序"""
    newer, older = await _seed_reversed_order(session, default_user.id)
    resp = (await client.get("/articles/?sort=create_at", headers=auth_headers)).json()
    assert [item["slug"] for item in resp["data"]] == [newer.slug, older.slug]


async def test_anonymous_select_id(client, session, default_user):
    """前台显式 sort=id → 发布 id 倒序"""
    newer, older = await _seed_reversed_order(session, default_user.id)
    resp = (await client.get("/articles/?sort=id")).json()
    assert [item["slug"] for item in resp["data"]] == [older.slug, newer.slug]


async def test_create_at_tie_falls_back_to_id_desc(client, session, default_user):
    """create_at 相同时按 id 倒序兜底，保证分页顺序确定"""
    same_time = datetime.now(timezone.utc)
    first = await _create_article(session, default_user.id, same_time, "同一时间先创建")
    second = await _create_article(session, default_user.id, same_time, "同一时间后创建")

    resp = (await client.get("/articles/")).json()
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


async def test_trash_list_sort_default_and_date(
    client, session, default_user, auth_headers
):
    """回收站列表：登录默认 id 倒序，显式 sort=create_at 改为发布时间倒序"""
    newer, older = await _seed_reversed_order(session, default_user.id)
    await ArticleService(session).delete(newer.slug)
    await ArticleService(session).delete(older.slug)

    by_default = (
        await client.get("/articles/?is_deleted=true", headers=auth_headers)
    ).json()
    assert [item["slug"] for item in by_default["data"]] == [older.slug, newer.slug]

    by_date = (
        await client.get(
            "/articles/?is_deleted=true&sort=create_at", headers=auth_headers
        )
    ).json()
    assert [item["slug"] for item in by_date["data"]] == [newer.slug, older.slug]


async def test_user_filter_defaults_to_create_at_desc_for_logged_in(
    client, session, default_user, auth_headers
):
    """查看用户文章（带 user_id 过滤）：登录态也默认按发布时间倒序"""
    newer, older = await _seed_reversed_order(session, default_user.id)
    resp = (
        await client.get(f"/articles/?user_id={default_user.id}", headers=auth_headers)
    ).json()
    assert [item["slug"] for item in resp["data"]] == [newer.slug, older.slug]


async def test_user_filter_defaults_to_create_at_desc_for_superadmin(
    client, session, default_user, superadmin_headers
):
    """超管按作者过滤查看用户文章：默认同样按发布时间倒序"""
    newer, older = await _seed_reversed_order(session, default_user.id)
    resp = (
        await client.get(
            f"/articles/?user_id={default_user.id}", headers=superadmin_headers
        )
    ).json()
    assert [item["slug"] for item in resp["data"]] == [newer.slug, older.slug]


async def test_user_filter_explicit_sort_id_still_wins(
    client, session, default_user, auth_headers
):
    """显式 sort=id 优先于「带 user_id 默认时间倒序」的新规则"""
    newer, older = await _seed_reversed_order(session, default_user.id)
    resp = (
        await client.get(
            f"/articles/?user_id={default_user.id}&sort=id", headers=auth_headers
        )
    ).json()
    assert [item["slug"] for item in resp["data"]] == [older.slug, newer.slug]


async def test_infinite_user_filter_defaults_to_create_at_desc_for_logged_in(
    client, session, default_user, auth_headers
):
    """查看用户文章（无限滚动）：登录态默认按发布时间倒序"""
    newer, older = await _seed_reversed_order(session, default_user.id)
    resp = (
        await client.get(
            f"/articles/infinite?user_id={default_user.id}", headers=auth_headers
        )
    ).json()
    assert [item["slug"] for item in resp["data"]] == [newer.slug, older.slug]
