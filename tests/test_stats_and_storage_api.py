"""搜索耗时、发布量统计、站点容量三个接口的行为测试。

- GET /articles/search 返回 elapsed_ms（前端据此展示「本次搜索耗时」）
- GET /articles/stats 按角色给出不同口径（超管=本月新增 / 普通用户=本人近半月）
- GET /base/storage 需登录，返回磁盘总量/已用/剩余
"""

from datetime import datetime, timedelta

from app.model import Article


async def _add_article(session, *, user_id: int, title: str, create_at: datetime) -> Article:
    article = Article(
        title=title,
        slug=f"slug-{title}-{int(create_at.timestamp())}",
        content=f"{title} 正文，用于搜索耗时与统计测试。",
        user_id=user_id,
        create_at=create_at,
    )
    session.add(article)
    await session.flush()
    return article


async def test_search_returns_elapsed_ms(client):
    res = await client.get("/articles/search", params={"keyword": "泵站"})
    assert res.status_code == 200
    body = res.json()
    assert "elapsed_ms" in body
    assert body["elapsed_ms"] >= 0
    # 原有分页字段保持不变
    for key in ("data", "total", "page", "page_size", "has_next"):
        assert key in body


async def test_search_elapsed_ms_requires_keyword(client):
    res = await client.get("/articles/search", params={"keyword": " "})
    assert res.status_code == 422


async def test_stats_requires_login(client):
    res = await client.get("/articles/stats")
    assert res.status_code in (401, 403)


async def test_stats_superadmin_counts_current_month(
    client, session, default_user, superadmin, superadmin_headers
):
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # 本月初 1 秒（本月，计入）与 上月（不计入）
    await _add_article(session, user_id=default_user.id, title="本月文章", create_at=month_start + timedelta(seconds=1))
    await _add_article(session, user_id=superadmin.id, title="上月的文章", create_at=month_start - timedelta(days=1))

    res = await client.get("/articles/stats", headers=superadmin_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["scope"] == "month"
    assert body["label"] == "本月新增文章"
    assert body["count"] == 1


async def test_stats_normal_user_counts_own_last_half_month(
    client, session, default_user, superadmin, auth_headers
):
    now = datetime.now()
    await _add_article(session, user_id=default_user.id, title="三天前", create_at=now - timedelta(days=3))
    await _add_article(session, user_id=default_user.id, title="二十天前", create_at=now - timedelta(days=20))
    # 他人文章不计入普通用户统计
    await _add_article(session, user_id=superadmin.id, title="超管的文章", create_at=now - timedelta(days=1))

    res = await client.get("/articles/stats", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["scope"] == "half_month"
    assert body["label"] == "我的近半月发布"
    assert body["count"] == 1


async def test_stats_excludes_deleted_articles(client, session, default_user, auth_headers):
    now = datetime.now()
    article = await _add_article(session, user_id=default_user.id, title="已删除", create_at=now - timedelta(days=1))
    article.is_deleted = True
    await session.flush()

    res = await client.get("/articles/stats", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["count"] == 0


async def test_storage_requires_login(client):
    res = await client.get("/base/storage")
    assert res.status_code in (401, 403)


async def test_storage_returns_disk_usage(client, auth_headers):
    res = await client.get("/base/storage", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["total"] > 0
    assert body["free"] >= 0
    assert body["used"] >= 0
    assert 0 <= body["usage_percent"] <= 100
    assert "uploads_bytes" in body
