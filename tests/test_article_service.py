import pytest
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
    updated = await service.update(out.slug, ArticleUpdate(title="新标题"))
    assert updated.title == "新标题"
    assert updated.content == "旧内容"
    assert await service.delete(out.slug) is True
    assert await service.get_by_slug(out.slug) is None


async def test_create_with_category(session, default_user):
    cat_service = CategoryService(session)
    cat = await cat_service.create(CategoryCreate(name="财务", slug="caiwu"))
    service = ArticleService(session)
    out = await service.create(ArticleCreate(title="标题", category_ids=[cat.id]))
    assert [c.id for c in out.categories] == [cat.id]


async def test_update_clears_nullable_fields(session, default_user):
    """显式传 null 应把 content/cover_img_slug 清空"""
    service = ArticleService(session)
    out = await service.create(ArticleCreate(title="T", content="内容", cover_img_slug="cov"))
    updated = await service.update(
        out.slug, ArticleUpdate(content=None, cover_img_slug=None)
    )
    assert updated.content is None
    assert updated.cover_img_slug is None


async def test_update_null_title_raises(session, default_user):
    """非空字段（title）显式传 null 应报错而非静默忽略或 500"""
    service = ArticleService(session)
    out = await service.create(ArticleCreate(title="T", content="内容"))
    with pytest.raises(ValueError):
        await service.update(out.slug, ArticleUpdate(title=None))
    # 原值不受影响
    got = await service.get_by_slug(out.slug)
    assert got.title == "T"


async def test_get_by_slug_service(session, default_user):
    service = ArticleService(session)
    out = await service.create(ArticleCreate(title="slug详情"))
    got = await service.get_by_slug(out.slug)
    assert got is not None
    assert got.id == out.id
    assert got.content is None
    assert await service.get_by_slug("no-such-slug") is None
