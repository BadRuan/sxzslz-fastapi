"""文章无限滚动 API 层测试：GET /articles/infinite

可见范围规则与 GET /articles/ 完全一致（匿名=公开全量、普通用户=强制本人、
超管=全量可过滤）；游标为 (create_at, id) 双键，同 create_at 翻页无重复无遗漏。
"""
from datetime import datetime

from app.dao import CategoryCrud
from app.schema import ArticleCreate
from app.service import ArticleService


async def _create(session, title, create_at=None, category_ids=None):
    return await ArticleService(session).create(
        ArticleCreate(
            title=title,
            content="正文",
            create_at=create_at,
            category_ids=category_ids or [],
        )
    )


async def test_infinite_pagination_no_dup_no_miss(client, session):
    """同 create_at 双键翻页：limit=2 翻 3 页合并 == 全部文章，无重复；末页收尾。"""
    same = datetime(2026, 1, 1, 12, 0, 0)
    created = []
    for i, ts in enumerate(
        [
            datetime(2026, 1, 5, 9, 0, 0),
            same,
            same,  # 与上一篇同一时间戳，必须靠 id 双键消歧
            datetime(2026, 1, 3, 9, 0, 0),
            datetime(2026, 1, 2, 9, 0, 0),
        ]
    ):
        out = await _create(session, f"文章{i}", create_at=ts)
        created.append(out.id)

    seen: list[int] = []
    cursor = None
    for _ in range(3):
        url = "/articles/infinite?limit=2"
        if cursor:
            url += f"&cursor={cursor}"
        resp = await client.get(url)
        assert resp.status_code == 200
        body = resp.json()
        seen.extend(item["id"] for item in body["data"])
        assert body["limit"] == 2
        if body["has_more"]:
            assert body["next_cursor"]
            cursor = body["next_cursor"]
        else:
            assert body["next_cursor"] is None

    assert sorted(seen) == sorted(created)
    assert len(seen) == len(set(seen))


async def test_infinite_scoped_by_role(client, session, auth_headers, superadmin_headers, default_user):
    """普通用户强制只看本人（user_id 参数无效）；匿名返回全部。"""
    resp = await client.post(
        "/articles/", json={"title": "普通用户文章"}, headers=auth_headers
    )
    assert resp.status_code == 201
    my_id = resp.json()["user"]["id"]

    resp2 = await client.post(
        "/articles/", json={"title": "超管文章一"}, headers=superadmin_headers
    )
    assert resp2.status_code == 201
    admin_id = resp2.json()["user"]["id"]
    await client.post(
        "/articles/", json={"title": "超管文章二"}, headers=superadmin_headers
    )

    # 普通用户传别人的 user_id 无效，只见自己
    resp3 = await client.get(
        f"/articles/infinite?user_id={admin_id}", headers=auth_headers
    )
    assert resp3.status_code == 200
    data = resp3.json()["data"]
    assert [a["title"] for a in data] == ["普通用户文章"]
    assert data[0]["user"]["id"] == my_id

    # 匿名见全部 3 篇
    resp4 = await client.get("/articles/infinite")
    assert resp4.status_code == 200
    assert len(resp4.json()["data"]) == 3


async def test_infinite_keyword_and_category_filter(client, session):
    """keyword 多词 AND 过滤；category_id 只返回挂该二级分类的文章。"""
    parent = await CategoryCrud(session).create(name="一级", parent_id=0, sort=0)
    cat = await CategoryCrud(session).create(name="二级", parent_id=parent.id, sort=0)
    other = await CategoryCrud(session).create(name="另二级", parent_id=parent.id, sort=1)

    await _create(session, "苹果香蕉橘子", category_ids=[cat.id])
    await _create(session, "苹果 西瓜 香蕉", category_ids=[cat.id])
    await _create(session, "苹果 西瓜", category_ids=[other.id])

    resp = await client.get("/articles/infinite?keyword=苹果 香蕉")
    assert resp.status_code == 200
    titles = [a["title"] for a in resp.json()["data"]]
    assert sorted(titles) == ["苹果 西瓜 香蕉", "苹果香蕉橘子"]

    resp2 = await client.get(f"/articles/infinite?category_id={cat.id}")
    assert resp2.status_code == 200
    titles2 = sorted(a["title"] for a in resp2.json()["data"])
    assert titles2 == ["苹果 西瓜 香蕉", "苹果香蕉橘子"]


async def test_infinite_invalid_cursor_400(client):
    resp = await client.get("/articles/infinite?cursor=not-a-cursor")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "无效的游标"


async def test_infinite_limit_bounds_422(client):
    resp0 = await client.get("/articles/infinite?limit=0")
    assert resp0.status_code == 422
    resp101 = await client.get("/articles/infinite?limit=101")
    assert resp101.status_code == 422
