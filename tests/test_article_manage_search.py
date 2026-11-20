"""GET /articles/ 标题搜索：后台管理按标题定位文章后编辑，权限可见范围不变。"""
from datetime import datetime, timedelta, timezone

from app.model import User
from app.schema import ArticleCreate, CategoryCreate
from app.service import ArticleService, CategoryService


async def _create_article(
    session,
    user_id: int,
    *,
    title: str,
    content: str | None = None,
    create_at: datetime | None = None,
    category_ids: list[int] | None = None,
):
    return await ArticleService(session).create(
        ArticleCreate(
            title=title,
            content=content,
            create_at=create_at,
            category_ids=category_ids or [],
        ),
        user_id=user_id,
    )


async def _create_user(session, username: str) -> User:
    user = User.create_user(username=username, nickname=username, password="test123")
    session.add(user)
    await session.flush()
    return user


async def _list(client, *, headers: dict | None = None, **params) -> dict:
    response = await client.get("/articles/", params=params, headers=headers or {})
    assert response.status_code == 200, response.text
    return response.json()


async def test_superadmin_searches_titles_across_authors(
    client, session, default_user, superadmin_headers
):
    """超管后台按标题搜全量文章：只匹配标题，正文命中不算；默认 id 倒序"""
    other = await _create_user(session, "other")
    first = await _create_article(
        session, default_user.id, title="泵站托管服务公告", content="无关正文"
    )
    second = await _create_article(
        session, other.id, title="年度泵站检修计划", content="无关正文"
    )
    await _create_article(
        session, other.id, title="普通公告", content="<p>正文里出现泵站</p>"
    )

    payload = await _list(client, headers=superadmin_headers, keyword="泵站")

    assert payload["total"] == 2
    assert [item["slug"] for item in payload["data"]] == [second.slug, first.slug]


async def test_superadmin_searches_recycle_bin_then_restores_and_edits(
    client, session, default_user, superadmin_headers
):
    """回收站也可按标题搜索定位，恢复后再编辑标题"""
    article = await _create_article(
        session, default_user.id, title="待恢复的泵站公告"
    )
    await ArticleService(session).delete(article.slug)

    assert (await _list(client, headers=superadmin_headers, keyword="泵站"))[
        "total"
    ] == 0

    trash = await _list(
        client,
        headers=superadmin_headers,
        keyword="泵站",
        is_deleted="true",
    )
    assert trash["total"] == 1
    assert trash["data"][0]["slug"] == article.slug

    restored = await client.post(
        f"/articles/{article.slug}/restore", headers=superadmin_headers
    )
    assert restored.status_code == 200, restored.text

    edited = await client.patch(
        f"/articles/{article.slug}",
        json={"title": "已恢复的泵站公告"},
        headers=superadmin_headers,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["title"] == "已恢复的泵站公告"

    payload = await _list(client, headers=superadmin_headers, keyword="已恢复")
    assert [item["slug"] for item in payload["data"]] == [article.slug]


async def test_keyword_combines_with_author_and_category_filters(
    client, session, default_user, superadmin_headers
):
    """超管可把标题搜索与 user_id / category_id 组合，交集生效"""
    other = await _create_user(session, "other")
    parent = await CategoryService(session).create(CategoryCreate(name="搜索一级"))
    child = await CategoryService(session).create(
        CategoryCreate(name="搜索二级", parent_id=parent.id)
    )
    mine = await _create_article(
        session,
        default_user.id,
        title="泵站A",
        category_ids=[child.id],
    )
    mine_uncategorized = await _create_article(
        session, default_user.id, title="泵站B"
    )
    others = await _create_article(session, other.id, title="泵站C")

    by_author = await _list(
        client, headers=superadmin_headers, keyword="泵站", user_id=default_user.id
    )
    assert by_author["total"] == 2
    assert {item["slug"] for item in by_author["data"]} == {
        mine.slug,
        mine_uncategorized.slug,
    }

    by_other = await _list(
        client, headers=superadmin_headers, keyword="泵站", user_id=other.id
    )
    assert [item["slug"] for item in by_other["data"]] == [others.slug]

    by_category = await _list(
        client, headers=superadmin_headers, keyword="泵站", category_id=child.id
    )
    assert [item["slug"] for item in by_category["data"]] == [mine.slug]


async def test_normal_user_keyword_search_scoped_to_own_articles(
    client, session, default_user, auth_headers, superadmin_headers
):
    """普通用户后台搜标题只返回自己的文章，user_id 参数被忽略；超管能看到全部"""
    other = await _create_user(session, "other")
    mine = await _create_article(session, default_user.id, title="我的泵站公告")
    theirs = await _create_article(session, other.id, title="他人泵站公告")

    own_scope = await _list(client, headers=auth_headers, keyword="泵站")
    assert own_scope["total"] == 1
    assert own_scope["data"][0]["slug"] == mine.slug

    ignored_author = await _list(
        client, headers=auth_headers, keyword="泵站", user_id=other.id
    )
    assert [item["slug"] for item in ignored_author["data"]] == [mine.slug]

    admin_scope = await _list(client, headers=superadmin_headers, keyword="泵站")
    assert {item["slug"] for item in admin_scope["data"]} == {mine.slug, theirs.slug}


async def test_anonymous_keyword_search_is_public_but_excludes_deleted(
    client, session, default_user
):
    """前台匿名也可用 keyword 过滤公开列表：全量未删文章，不收敛为本人"""
    other = await _create_user(session, "other")
    alive = await _create_article(session, other.id, title="公开泵站公告")
    deleted = await _create_article(session, default_user.id, title="已删泵站公告")
    await ArticleService(session).delete(deleted.slug)

    payload = await _list(client, keyword="泵站")

    assert payload["total"] == 1
    assert payload["data"][0]["slug"] == alive.slug


async def test_keyword_is_case_insensitive_and_supports_multi_terms(
    client, session, default_user
):
    """英文大小写不敏感；多个词用空格分隔，需全部命中标题（AND）"""
    matched = await _create_article(
        session, default_user.id, title="FastAPI 泵站指南"
    )
    await _create_article(session, default_user.id, title="FastAPI 入门")

    single = await _list(client, keyword="fastapi")
    assert single["total"] == 2

    multi = await _list(client, keyword="FASTAPI 指南")
    assert multi["total"] == 1
    assert multi["data"][0]["slug"] == matched.slug

    chinese = await _list(client, keyword="泵站 指南")
    assert [item["slug"] for item in chinese["data"]] == [matched.slug]


async def test_keyword_treats_like_wildcards_as_literals(
    client, session, default_user
):
    """% / _ 按字面量匹配，不会变成通配符"""
    percent = await _create_article(session, default_user.id, title="完成度 100%")
    await _create_article(session, default_user.id, title="完成度 1000")
    await _create_article(session, default_user.id, title="普通标题")

    percent_payload = await _list(client, keyword="100%")
    assert percent_payload["total"] == 1
    assert percent_payload["data"][0]["slug"] == percent.slug

    assert (await _list(client, keyword="%"))["total"] == 1
    assert (await _list(client, keyword="_"))["total"] == 0


async def test_keyword_validation_returns_422(client):
    """空关键词 / 纯空白 / 超过 50 字 → 422（与 /articles/search 口径一致）"""
    assert (await client.get("/articles/", params={"keyword": ""})).status_code == 422

    blank = await client.get("/articles/", params={"keyword": "   "})
    assert blank.status_code == 422
    assert blank.json()["detail"] == "关键词不能为空"

    too_long = await client.get("/articles/", params={"keyword": "x" * 51})
    assert too_long.status_code == 422


async def test_keyword_search_pagination_and_stable_order(
    client, session, default_user
):
    """标题搜索分页：total 只统计命中项，匿名默认发布时间倒序，翻页稳定"""
    now = datetime.now(timezone.utc)
    oldest = await _create_article(
        session, default_user.id, title="泵站旧公告", create_at=now - timedelta(days=2)
    )
    middle = await _create_article(
        session, default_user.id, title="泵站中公告", create_at=now - timedelta(days=1)
    )
    newest = await _create_article(
        session, default_user.id, title="泵站新公告", create_at=now
    )
    await _create_article(session, default_user.id, title="无关公告", create_at=now)

    first_page = await _list(client, keyword="泵站", page=1, page_size=2)
    assert first_page["total"] == 3
    assert first_page["has_next"] is True
    assert [item["slug"] for item in first_page["data"]] == [
        newest.slug,
        middle.slug,
    ]

    second_page = await _list(client, keyword="泵站", page=2, page_size=2)
    assert second_page["has_next"] is False
    assert [item["slug"] for item in second_page["data"]] == [oldest.slug]


async def test_keyword_no_match_returns_empty_page(
    client, session, default_user
):
    await _create_article(session, default_user.id, title="普通公告")

    payload = await _list(client, keyword="不存在的标题")

    assert payload["total"] == 0
    assert payload["data"] == []
    assert payload["has_next"] is False