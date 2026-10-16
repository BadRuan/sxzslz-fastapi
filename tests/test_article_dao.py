import pytest
from app.dao import ArticleCrud, CategoryCrud


async def test_create_article_with_categories(session, default_user):
    cat_crud = CategoryCrud(session)
    cat = await cat_crud.create(name="财务", slug="caiwu", parent_id=0, sort=0)

    crud = ArticleCrud(session)
    article = await crud.create(
        title="标题",
        content="内容",
        cover_img_slug=None,
        is_hidden=False,
        is_recommended=False,
        user_id=default_user.id,
        category_ids=[cat.id],
    )
    assert article.id is not None
    loaded = await crud.get_by_id(article.id)
    assert loaded is not None
    assert loaded.title == "标题"
    assert [c.id for c in loaded.categories] == [cat.id]


async def test_create_with_invalid_category_raises(session, default_user):
    crud = ArticleCrud(session)
    with pytest.raises(ValueError):
        await crud.create(
            title="标题",
            content=None,
            cover_img_slug=None,
            is_hidden=False,
            is_recommended=False,
            user_id=default_user.id,
            category_ids=[999],
        )


async def test_list_paginated(session, default_user):
    crud = ArticleCrud(session)
    for i in range(5):
        await crud.create(
            title=f"标题{i}",
            content=None,
            cover_img_slug=None,
            is_hidden=False,
            is_recommended=False,
            user_id=default_user.id,
            category_ids=[],
        )
    items, total = await crud.list_paginated(page=1, page_size=2)
    assert total == 5
    assert len(items) == 2

    items2, _ = await crud.list_paginated(page=3, page_size=2)
    assert len(items2) == 1


async def test_list_paginated_filter_category(session, default_user):
    cat_crud = CategoryCrud(session)
    cat1 = await cat_crud.create(name="A", slug="a", parent_id=0, sort=0)
    cat2 = await cat_crud.create(name="B", slug="b", parent_id=0, sort=0)

    crud = ArticleCrud(session)
    await crud.create(
        title="在A", content=None, cover_img_slug=None,
        is_hidden=False, is_recommended=False, user_id=default_user.id, category_ids=[cat1.id],
    )
    await crud.create(
        title="在B", content=None, cover_img_slug=None,
        is_hidden=False, is_recommended=False, user_id=default_user.id, category_ids=[cat2.id],
    )

    items, total = await crud.list_paginated(page=1, page_size=10, category_id=cat1.id)
    assert total == 1
    assert items[0].title == "在A"


async def test_soft_delete(session, default_user):
    crud = ArticleCrud(session)
    article = await crud.create(
        title="x", content=None, cover_img_slug=None,
        is_hidden=False, is_recommended=False, user_id=default_user.id, category_ids=[],
    )
    assert await crud.soft_delete(article.id) is True
    assert await crud.get_by_id(article.id) is None
    assert await crud.soft_delete(article.id) is False
