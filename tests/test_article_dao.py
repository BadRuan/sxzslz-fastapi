import pytest

from app.dao import ArticleCrud, CategoryCrud


async def _level2_cat(cat_crud: CategoryCrud, parent_name: str, child_name: str):
    parent = await cat_crud.create(name=parent_name, parent_id=0, sort=0)
    return await cat_crud.create(name=child_name, parent_id=parent.id, sort=0)


async def test_create_article_with_categories(session, default_user):
    cat_crud = CategoryCrud(session)
    cat = await _level2_cat(cat_crud, "财务", "招标")

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
    loaded = await crud.get_by_slug(article.slug)
    assert loaded is not None
    assert loaded.title == "标题"
    assert [c.id for c in loaded.categories] == [cat.id]


async def test_create_with_multiple_level2_categories(session, default_user):
    """单篇文章可同时属于多个二级分类"""
    cat_crud = CategoryCrud(session)
    parent = await cat_crud.create(name="财务", parent_id=0, sort=0)
    cat1 = await cat_crud.create(name="招标", parent_id=parent.id, sort=0)
    cat2 = await cat_crud.create(name="预算", parent_id=parent.id, sort=0)

    crud = ArticleCrud(session)
    article = await crud.create(
        title="多分类", content=None, cover_img_slug=None,
        is_hidden=False, is_recommended=False,
        user_id=default_user.id, category_ids=[cat1.id, cat2.id],
    )
    loaded = await crud.get_by_slug(article.slug)
    assert {c.id for c in loaded.categories} == {cat1.id, cat2.id}


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


async def test_create_with_level1_category_raises(session, default_user):
    """文章仅支持关联二级分类"""
    cat_crud = CategoryCrud(session)
    top = await cat_crud.create(name="一级", parent_id=0, sort=0)

    crud = ArticleCrud(session)
    with pytest.raises(ValueError):
        await crud.create(
            title="标题", content=None, cover_img_slug=None,
            is_hidden=False, is_recommended=False,
            user_id=default_user.id, category_ids=[top.id],
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
    cat1 = await _level2_cat(cat_crud, "P1", "A")
    cat2 = await _level2_cat(cat_crud, "P2", "B")

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


async def test_list_paginated_exact_match_no_subtree(session, default_user):
    """查询仅走二级分类：按一级分类查询不聚合子分类文章"""
    cat_crud = CategoryCrud(session)
    parent = await cat_crud.create(name="父", parent_id=0, sort=0)
    child = await cat_crud.create(name="子", parent_id=parent.id, sort=0)
    sibling = await cat_crud.create(name="兄弟", parent_id=0, sort=0)
    other_child = await cat_crud.create(name="他子", parent_id=sibling.id, sort=0)

    crud = ArticleCrud(session)
    await crud.create(
        title="子下文章", content=None, cover_img_slug=None,
        is_hidden=False, is_recommended=False,
        user_id=default_user.id, category_ids=[child.id],
    )
    await crud.create(
        title="他子下", content=None, cover_img_slug=None,
        is_hidden=False, is_recommended=False,
        user_id=default_user.id, category_ids=[other_child.id],
    )

    # 一级分类：不聚合子分类文章
    items, total = await crud.list_paginated(page=1, page_size=10, category_id=parent.id)
    assert total == 0
    assert items == []

    # 二级分类：仅命中自身
    items, total = await crud.list_paginated(page=1, page_size=10, category_id=child.id)
    assert total == 1
    assert items[0].title == "子下文章"

    # 分类不存在：空分页，不报错
    items, total = await crud.list_paginated(page=1, page_size=10, category_id=999)
    assert total == 0
    assert items == []


async def test_list_paginated_multi_category_no_duplicate(session, default_user):
    """文章挂多个二级分类时，按其中一个过滤不应出现重复行"""
    cat_crud = CategoryCrud(session)
    parent = await cat_crud.create(name="父", parent_id=0, sort=0)
    c1 = await cat_crud.create(name="子1", parent_id=parent.id, sort=0)
    c2 = await cat_crud.create(name="子2", parent_id=parent.id, sort=0)

    crud = ArticleCrud(session)
    await crud.create(
        title="双挂", content=None, cover_img_slug=None,
        is_hidden=False, is_recommended=False,
        user_id=default_user.id, category_ids=[c1.id, c2.id],
    )

    items, total = await crud.list_paginated(page=1, page_size=10, category_id=c1.id)
    assert total == 1
    assert len(items) == 1


async def test_list_paginated_deleted_category(session, default_user):
    """分类删除后，按其过滤应返回空"""
    cat_crud = CategoryCrud(session)
    cat = await _level2_cat(cat_crud, "父", "将删")

    crud = ArticleCrud(session)
    await crud.create(
        title="文章", content=None, cover_img_slug=None,
        is_hidden=False, is_recommended=False,
        user_id=default_user.id, category_ids=[cat.id],
    )
    await cat_crud.delete(cat.id)

    items, total = await crud.list_paginated(page=1, page_size=10, category_id=cat.id)
    assert total == 0
    assert items == []


async def test_article_excludes_deleted_category(session, default_user):
    """分类删除后，文章详情中不应再出现该分类"""
    cat_crud = CategoryCrud(session)
    cat = await _level2_cat(cat_crud, "父", "隐藏分类")

    crud = ArticleCrud(session)
    art = await crud.create(
        title="T", content=None, cover_img_slug=None,
        is_hidden=False, is_recommended=False,
        user_id=default_user.id, category_ids=[cat.id],
    )
    slug = art.slug
    await cat_crud.delete(cat.id)
    # 模拟新请求的新 session：强制重新加载关联
    session.expire_all()

    loaded = await crud.get_by_slug(slug)
    assert loaded is not None
    assert loaded.categories == []


async def test_get_by_slug(session, default_user):
    cat_crud = CategoryCrud(session)
    cat = await _level2_cat(cat_crud, "会议", "纪要")

    crud = ArticleCrud(session)
    created = await crud.create(
        title="slug文章", content="内容", cover_img_slug=None,
        is_hidden=False, is_recommended=False,
        user_id=default_user.id, category_ids=[cat.id],
    )

    loaded = await crud.get_by_slug(created.slug)
    assert loaded is not None
    assert loaded.id == created.id
    assert loaded.title == "slug文章"
    assert [c.id for c in loaded.categories] == [cat.id]

    assert await crud.get_by_slug("no-such-slug") is None


async def test_update_replaces_categories(session, default_user):
    """更新 category_ids 应整体替换关联（单篇可属多个二级分类）"""
    cat_crud = CategoryCrud(session)
    parent = await cat_crud.create(name="父", parent_id=0, sort=0)
    c1 = await cat_crud.create(name="子1", parent_id=parent.id, sort=0)
    c2 = await cat_crud.create(name="子2", parent_id=parent.id, sort=1)

    crud = ArticleCrud(session)
    art = await crud.create(
        title="T", content=None, cover_img_slug=None,
        is_hidden=False, is_recommended=False,
        user_id=default_user.id, category_ids=[c1.id],
    )
    updated = await crud.update(art.slug, category_ids=[c1.id, c2.id])
    assert {c.id for c in updated.categories} == {c1.id, c2.id}

    updated = await crud.update(art.slug, category_ids=[c2.id])
    assert [c.id for c in updated.categories] == [c2.id]


async def test_update_clears_categories_with_null(session, default_user):
    """显式传 null / 空列表应清空全部分类关联"""
    cat_crud = CategoryCrud(session)
    cat = await _level2_cat(cat_crud, "父", "将清空")

    crud = ArticleCrud(session)
    art = await crud.create(
        title="T", content=None, cover_img_slug=None,
        is_hidden=False, is_recommended=False,
        user_id=default_user.id, category_ids=[cat.id],
    )
    updated = await crud.update(art.slug, category_ids=None)
    assert updated.categories == []

    art2 = await crud.create(
        title="T2", content=None, cover_img_slug=None,
        is_hidden=False, is_recommended=False,
        user_id=default_user.id, category_ids=[cat.id],
    )
    updated = await crud.update(art2.slug, category_ids=[])
    assert updated.categories == []


async def test_update_with_level1_category_raises(session, default_user):
    """更新时也不能关联一级分类"""
    cat_crud = CategoryCrud(session)
    top = await cat_crud.create(name="一级", parent_id=0, sort=0)

    crud = ArticleCrud(session)
    art = await crud.create(
        title="T", content=None, cover_img_slug=None,
        is_hidden=False, is_recommended=False,
        user_id=default_user.id, category_ids=[],
    )
    with pytest.raises(ValueError):
        await crud.update(art.slug, category_ids=[top.id])


async def test_update_invalid_field_does_not_touch_categories(session, default_user):
    """非空字段校验失败时，已解析的分类不应落库（先校验后赋值）"""
    cat_crud = CategoryCrud(session)
    c1 = await _level2_cat(cat_crud, "P1", "C1")
    c2 = await _level2_cat(cat_crud, "P2", "C2")

    crud = ArticleCrud(session)
    art = await crud.create(
        title="T", content=None, cover_img_slug=None,
        is_hidden=False, is_recommended=False,
        user_id=default_user.id, category_ids=[c1.id],
    )
    slug = art.slug
    with pytest.raises(ValueError):
        await crud.update(slug, title=None, category_ids=[c2.id])

    session.expire_all()
    loaded = await crud.get_by_slug(slug)
    assert loaded.title == "T"
    assert [c.id for c in loaded.categories] == [c1.id]
