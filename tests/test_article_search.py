"""GET /articles/search 的 API 行为测试：匹配、摘要、范围、排序、分页与校验。"""
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


async def _search(client, **params):
    response = await client.get("/articles/search", params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def test_search_matches_title_and_returns_metadata(
    client, session, default_user
):
    article = await _create_article(
        session,
        default_user.id,
        title="泵站托管服务公告",
        content="<p>与关键词无关的正文</p>",
    )

    payload = await _search(client, keyword="泵站")

    assert payload["total"] == 1
    item = payload["data"][0]
    assert item["slug"] == article.slug
    assert item["title"] == "泵站托管服务公告"
    assert "content" not in item
    assert item["content_snippet"] is None
    assert item["matched_terms"] == ["泵站"]
    assert item["matched_fields"] == ["title"]


async def test_search_matches_content_with_plain_text_snippet(
    client, session, default_user
):
    await _create_article(
        session,
        default_user.id,
        title="与关键词无关的标题",
        content="<p>本次<strong>泵站</strong>托管范围包括三座提升站。</p>",
    )

    item = (await _search(client, keyword="泵站"))["data"][0]

    assert item["matched_fields"] == ["content"]
    assert "泵站" in item["content_snippet"]
    assert "<p>" not in item["content_snippet"]
    assert "<strong>" not in item["content_snippet"]


async def test_search_reports_both_fields_when_title_and_content_match(
    client, session, default_user
):
    await _create_article(
        session,
        default_user.id,
        title="泵站托管公告",
        content="<p>泵站设备台账</p>",
    )

    item = (await _search(client, keyword="泵站"))["data"][0]

    assert item["matched_fields"] == ["title", "content"]
    assert item["content_snippet"] is not None


async def test_search_is_case_insensitive_for_english_keywords(
    client, session, default_user
):
    await _create_article(
        session, default_user.id, title="FastAPI 入门指南", content=None
    )

    item = (await _search(client, keyword="fastapi"))["data"][0]

    assert item["matched_terms"] == ["fastapi"]
    assert item["matched_fields"] == ["title"]


async def test_search_requires_all_terms_across_title_and_content(
    client, session, default_user
):
    await _create_article(
        session, default_user.id, title="泵站公告", content="托管服务范围"
    )
    await _create_article(
        session, default_user.id, title="泵站公告", content="其他内容"
    )

    payload = await _search(client, keyword="泵站 托管")

    assert payload["total"] == 1
    item = payload["data"][0]
    assert item["matched_terms"] == ["泵站", "托管"]
    assert item["matched_fields"] == ["title", "content"]


async def test_search_scope_limits_fields_and_snippet(
    client, session, default_user
):
    title_article = await _create_article(
        session, default_user.id, title="标题关键词甲", content="普通正文"
    )
    content_article = await _create_article(
        session, default_user.id, title="普通标题", content="<p>正文关键词乙</p>"
    )

    title_payload = await _search(
        client, keyword="标题关键词甲", scope="title"
    )
    assert [item["slug"] for item in title_payload["data"]] == [title_article.slug]
    assert title_payload["data"][0]["content_snippet"] is None

    assert (await _search(client, keyword="标题关键词甲", scope="content"))[
        "total"
    ] == 0

    content_payload = await _search(
        client, keyword="正文关键词乙", scope="content"
    )
    assert [item["slug"] for item in content_payload["data"]] == [
        content_article.slug
    ]
    assert content_payload["data"][0]["matched_fields"] == ["content"]
    assert "正文关键词乙" in content_payload["data"][0]["content_snippet"]

    assert (await _search(client, keyword="正文关键词乙", scope="title"))[
        "total"
    ] == 0


async def test_search_scope_title_never_returns_content_snippet(
    client, session, default_user
):
    await _create_article(
        session, default_user.id, title="泵站标题", content="<p>泵站正文</p>"
    )

    item = (await _search(client, keyword="泵站", scope="title"))["data"][0]

    assert item["matched_fields"] == ["title"]
    assert item["content_snippet"] is None


async def test_search_escapes_like_wildcards(client, session, default_user):
    percent_article = await _create_article(
        session, default_user.id, title="完成度 100%"
    )
    await _create_article(session, default_user.id, title="普通标题")

    percent_payload = await _search(client, keyword="100%")
    assert percent_payload["total"] == 1
    assert percent_payload["data"][0]["slug"] == percent_article.slug

    # 单独的 % / _ 按字面量匹配，不会变成“匹配全部”
    assert (await _search(client, keyword="%"))["total"] == 1
    assert (await _search(client, keyword="_"))["total"] == 0


async def test_search_excludes_deleted_articles(client, session, default_user):
    article = await _create_article(
        session, default_user.id, title="待删除泵站公告"
    )
    await ArticleService(session).delete(article.slug)

    payload = await _search(client, keyword="泵站")

    assert payload["total"] == 0
    assert payload["data"] == []


async def test_search_filters_by_exact_second_level_category(
    client, session, default_user
):
    parent = await CategoryService(session).create(
        CategoryCreate(name="搜索测试一级")
    )
    child = await CategoryService(session).create(
        CategoryCreate(name="搜索测试二级", parent_id=parent.id)
    )
    categorized = await _create_article(
        session,
        default_user.id,
        title="泵站分类文章",
        category_ids=[child.id],
    )
    await _create_article(session, default_user.id, title="泵站无分类文章")

    payload = await _search(client, keyword="泵站", category_id=child.id)

    assert payload["total"] == 1
    assert payload["data"][0]["slug"] == categorized.slug


async def test_search_orders_by_publish_time_desc_regardless_of_hit_field(
    client, session, default_user
):
    now = datetime.now(timezone.utc)
    older = await _create_article(
        session,
        default_user.id,
        title="泵站旧公告",
        content="标题命中",
        create_at=now - timedelta(days=2),
    )
    newer = await _create_article(
        session,
        default_user.id,
        title="新公告",
        content="<p>正文命中泵站</p>",
        create_at=now,
    )

    payload = await _search(client, keyword="泵站")

    assert [item["slug"] for item in payload["data"]] == [newer.slug, older.slug]


async def test_search_uses_id_desc_as_tie_breaker_for_same_publish_time(
    client, session, default_user
):
    create_at = datetime(2026, 1, 2, 3, 4, 5)
    first = await _create_article(
        session, default_user.id, title="泵站甲", create_at=create_at
    )
    second = await _create_article(
        session, default_user.id, title="泵站乙", create_at=create_at
    )

    payload = await _search(client, keyword="泵站")

    assert [item["slug"] for item in payload["data"]] == [second.slug, first.slug]


async def test_search_paginates_and_reports_has_next(
    client, session, default_user
):
    now = datetime.now(timezone.utc)
    articles = [
        await _create_article(
            session,
            default_user.id,
            title=f"泵站列表文章{index}",
            create_at=now - timedelta(hours=index),
        )
        for index in range(3)
    ]

    first_page = await _search(client, keyword="泵站", page=1, page_size=2)
    assert first_page["total"] == 3
    assert first_page["page"] == 1
    assert first_page["page_size"] == 2
    assert first_page["has_next"] is True
    assert [item["slug"] for item in first_page["data"]] == [
        articles[0].slug,
        articles[1].slug,
    ]

    second_page = await _search(client, keyword="泵站", page=2, page_size=2)
    assert second_page["has_next"] is False
    assert [item["slug"] for item in second_page["data"]] == [articles[2].slug]


async def test_search_returns_empty_page_when_nothing_matches(
    client, session, default_user
):
    await _create_article(session, default_user.id, title="泵站公告")

    payload = await _search(client, keyword="完全不存在")

    assert payload["total"] == 0
    assert payload["data"] == []
    assert payload["has_next"] is False


async def test_search_snippet_marks_truncation_with_ellipsis(
    client, session, default_user
):
    await _create_article(
        session,
        default_user.id,
        title="长正文",
        content="甲" * 60 + "泵站" + "乙" * 80,
    )

    snippet = (await _search(client, keyword="泵站"))["data"][0]["content_snippet"]

    assert snippet.startswith("…")
    assert snippet.endswith("…")
    assert "泵站" in snippet


async def test_search_snippet_never_returns_html_tags(
    client, session, default_user
):
    await _create_article(
        session,
        default_user.id,
        title="富文本正文",
        content="<p>正文</p><script>alert('泵站')</script>",
    )

    snippet = (await _search(client, keyword="泵站"))["data"][0]["content_snippet"]

    assert "<p>" not in snippet
    assert "<script>" not in snippet
    assert "泵站" in snippet


async def test_search_deduplicates_repeated_terms(
    client, session, default_user
):
    await _create_article(session, default_user.id, title="泵站公告")

    item = (await _search(client, keyword="泵站   泵站"))["data"][0]

    assert item["matched_terms"] == ["泵站"]


async def test_search_is_public_and_ignores_caller_scope(
    client, session, default_user, auth_headers
):
    other = User.create_user(
        username="other", nickname="其他作者", password="test123"
    )
    session.add(other)
    await session.flush()

    own = await _create_article(session, default_user.id, title="泵站本人文章")
    others = await _create_article(session, other.id, title="泵站他人文章")
    expected = {own.slug, others.slug}

    # 匿名可搜全量
    anonymous = await _search(client, keyword="泵站")
    assert {item["slug"] for item in anonymous["data"]} == expected

    # 普通用户带 token 也不收敛为本人；搜索接口不解析鉴权，非法 token 同样不 401
    authed = await client.get(
        "/articles/search", params={"keyword": "泵站"}, headers=auth_headers
    )
    assert authed.status_code == 200
    assert {item["slug"] for item in authed.json()["data"]} == expected

    invalid = await client.get(
        "/articles/search",
        params={"keyword": "泵站"},
        headers={"Authorization": "Bearer invalid"},
    )
    assert invalid.status_code == 200
    assert {item["slug"] for item in invalid.json()["data"]} == expected


async def test_search_rejects_missing_blank_or_too_long_keyword(client):
    assert (await client.get("/articles/search")).status_code == 422
    assert (
        await client.get("/articles/search", params={"keyword": "   "})
    ).status_code == 422
    assert (
        await client.get("/articles/search", params={"keyword": "泵" * 51})
    ).status_code == 422
    assert (
        await client.get(
            "/articles/search", params={"keyword": "泵站", "scope": "author"}
        )
    ).status_code == 422
