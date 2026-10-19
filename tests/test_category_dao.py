import pytest
from sqlmodel import select

from app.dao import ArticleCrud, CategoryCrud
from app.model import ArticleCategory


async def test_create_top_level(session):
    crud = CategoryCrud(session)
    category = await crud.create(name="新闻动态", parent_id=0, sort=0)
    assert category.id is not None
    assert category.parent_id == 0


async def test_create_child(session):
    crud = CategoryCrud(session)
    parent = await crud.create(name="财务信息", parent_id=0, sort=0)
    child = await crud.create(name="招标采购", parent_id=parent.id, sort=0)
    assert child.parent_id == parent.id


async def test_create_invalid_parent_raises(session):
    crud = CategoryCrud(session)
    with pytest.raises(ValueError):
        await crud.create(name="x", parent_id=9999, sort=0)


async def test_create_third_level_raises(session):
    """仅支持二级分类：二级分类下不能再挂子分类"""
    crud = CategoryCrud(session)
    parent = await crud.create(name="一级", parent_id=0, sort=0)
    child = await crud.create(name="二级", parent_id=parent.id, sort=0)
    with pytest.raises(ValueError):
        await crud.create(name="三级", parent_id=child.id, sort=0)


async def test_delete_removes(session):
    crud = CategoryCrud(session)
    category = await crud.create(name="临时", parent_id=0, sort=0)
    assert len(await crud.get_all()) == 1
    assert await crud.delete(category.id) is True
    assert await crud.get_all() == []
    assert await crud.delete(category.id) is False


async def test_delete_cascades_children(session):
    """删除一级分类应级联删除其子分类"""
    crud = CategoryCrud(session)
    a = await crud.create(name="A", parent_id=0, sort=0)
    b = await crud.create(name="B", parent_id=a.id, sort=0)
    d = await crud.create(name="D", parent_id=0, sort=0)

    assert await crud.delete(a.id) is True

    assert [x.id for x in await crud.get_all()] == [d.id]
    assert await crud.get_raw_by_id(b.id) is None
    assert await crud.get_raw_by_id(a.id) is None


async def test_delete_clears_article_links(session, default_user):
    """删除分类应清理文章关联（业务层外键），文章本体保留"""
    cat_crud = CategoryCrud(session)
    parent = await cat_crud.create(name="P", parent_id=0, sort=0)
    child = await cat_crud.create(name="C", parent_id=parent.id, sort=0)

    art_crud = ArticleCrud(session)
    art = await art_crud.create(
        title="T", content=None, cover_img_slug=None,
        is_hidden=False, is_recommended=False,
        user_id=default_user.id, category_ids=[child.id],
    )

    assert await cat_crud.delete(parent.id) is True

    art_id, slug = art.id, art.slug
    # 模拟新请求的新 session：强制重新加载关联
    session.expire_all()
    loaded = await art_crud.get_by_slug(slug)
    assert loaded is not None
    assert loaded.categories == []

    links = (await session.exec(
        select(ArticleCategory).where(ArticleCategory.article_id == art_id)
    )).all()
    assert links == []


async def test_update_fields(session):
    crud = CategoryCrud(session)
    category = await crud.create(name="旧名", parent_id=0, sort=0)
    updated = await crud.update(category.id, name="新名", sort=5)
    assert updated is not None
    assert updated.name == "新名"
    assert updated.sort == 5


async def test_update_parent_moves_level2(session):
    """二级分类可改挂到另一个一级分类下"""
    crud = CategoryCrud(session)
    a = await crud.create(name="A", parent_id=0, sort=0)
    b = await crud.create(name="B", parent_id=0, sort=0)
    child = await crud.create(name="C", parent_id=a.id, sort=0)

    updated = await crud.update(child.id, parent_id=b.id)
    assert updated.parent_id == b.id


async def test_update_parent_level1_raises(session):
    """一级分类不支持调整父级"""
    crud = CategoryCrud(session)
    a = await crud.create(name="A", parent_id=0, sort=0)
    b = await crud.create(name="B", parent_id=0, sort=0)
    with pytest.raises(ValueError):
        await crud.update(a.id, parent_id=b.id)


async def test_update_parent_to_top_raises(session):
    """二级分类不能调整为一级分类"""
    crud = CategoryCrud(session)
    a = await crud.create(name="A", parent_id=0, sort=0)
    child = await crud.create(name="C", parent_id=a.id, sort=0)
    with pytest.raises(ValueError):
        await crud.update(child.id, parent_id=0)


async def test_update_parent_to_level2_raises(session):
    """父分类必须是一级分类"""
    crud = CategoryCrud(session)
    a = await crud.create(name="A", parent_id=0, sort=0)
    c1 = await crud.create(name="C1", parent_id=a.id, sort=0)
    c2 = await crud.create(name="C2", parent_id=a.id, sort=0)
    with pytest.raises(ValueError):
        await crud.update(c1.id, parent_id=c2.id)


async def test_get_all_orders_by_sort(session):
    """分类按 sort 升序输出（排序调整）"""
    crud = CategoryCrud(session)
    await crud.create(name="B", parent_id=0, sort=2)
    await crud.create(name="A", parent_id=0, sort=1)
    await crud.create(name="C", parent_id=0, sort=3)
    assert [c.name for c in await crud.get_all()] == ["A", "B", "C"]


async def test_tree_two_level_structure(session):
    """分类树：一级分类下挂二级分类，二级分类 children 为空"""
    crud = CategoryCrud(session)
    parent = await crud.create(name="财务信息", parent_id=0, sort=0)
    await crud.create(name="招标采购", parent_id=parent.id, sort=0)
    await crud.create(name="预算公开", parent_id=parent.id, sort=1)
    await crud.create(name="单位概况", parent_id=0, sort=1)

    tree = await crud.get_tree_all()
    assert [n.name for n in tree] == ["财务信息", "单位概况"]
    assert [c.name for c in tree[0].children] == ["招标采购", "预算公开"]
    assert tree[0].children[0].children == []
    assert tree[1].children == []


async def test_tree_orders_by_sort(session):
    """同级节点按 sort 升序（一级与二级均适用）"""
    crud = CategoryCrud(session)
    a = await crud.create(name="一级B", parent_id=0, sort=2)
    await crud.create(name="一级A", parent_id=0, sort=1)
    await crud.create(name="子B", parent_id=a.id, sort=20)
    await crud.create(name="子A", parent_id=a.id, sort=10)

    tree = await crud.get_tree_all()
    assert [n.name for n in tree] == ["一级A", "一级B"]
    assert [c.name for c in tree[1].children] == ["子A", "子B"]
