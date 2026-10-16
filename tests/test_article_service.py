from app.service import ArticleService, CategoryService
from app.schema import ArticleCreate, ArticleUpdate, CategoryCreate


async def test_create_uses_default_user(session, default_user):
    service = ArticleService(session)
    out = await service.create(ArticleCreate(title="标题"))
    assert out.user is not None
    assert out.user.id == default_user.id


async def test_list_pagination_response(session, default_user):
    service = ArticleService(session)
    for i in range(3):
        await service.create(ArticleCreate(title=f"标题{i}"))
    page = await service.list_paginated(page=1, page_size=2)
    assert page.total == 3
    assert page.page == 1
    assert page.page_size == 2
    assert page.has_next is True
    assert len(page.data) == 2


async def test_update_and_delete(session, default_user):
    service = ArticleService(session)
    out = await service.create(ArticleCreate(title="旧标题", content="旧内容"))
    updated = await service.update(out.id, ArticleUpdate(title="新标题"))
    assert updated.title == "新标题"
    assert updated.content == "旧内容"
    assert await service.delete(out.id) is True
    assert await service.get(out.id) is None


async def test_create_with_category(session, default_user):
    cat_service = CategoryService(session)
    cat = await cat_service.create(CategoryCreate(name="财务", slug="caiwu"))
    service = ArticleService(session)
    out = await service.create(ArticleCreate(title="标题", category_ids=[cat.id]))
    assert [c.id for c in out.categories] == [cat.id]


async def test_get_by_slug_service(session, default_user):
    service = ArticleService(session)
    out = await service.create(ArticleCreate(title="slug详情"))
    got = await service.get_by_slug(out.slug)
    assert got is not None
    assert got.id == out.id
    assert got.content is None
    assert await service.get_by_slug("no-such-slug") is None
