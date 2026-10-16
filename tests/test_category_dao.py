import pytest
from app.dao import CategoryCrud


async def test_create_top_level(session):
    crud = CategoryCrud(session)
    category = await crud.create(name="新闻动态", slug="xinwen", parent_id=0, sort=0)
    assert category.id is not None
    assert category.level == 1
    assert category.path == f"/{category.id}/"


async def test_create_child(session):
    crud = CategoryCrud(session)
    parent = await crud.create(name="财务信息", slug="caiwu", parent_id=0, sort=0)
    child = await crud.create(name="招标采购", slug="caigou", parent_id=parent.id, sort=0)
    assert child.level == 2
    assert child.path == f"/{parent.id}/{child.id}/"


async def test_create_invalid_parent_raises(session):
    crud = CategoryCrud(session)
    with pytest.raises(ValueError):
        await crud.create(name="x", slug="x", parent_id=9999, sort=0)


async def test_soft_delete_filters_out(session):
    crud = CategoryCrud(session)
    category = await crud.create(name="临时", slug="linshi", parent_id=0, sort=0)
    assert len(await crud.get_active_all()) == 1
    assert await crud.soft_delete(category.id) is True
    assert await crud.get_active_all() == []
    assert await crud.soft_delete(category.id) is False


async def test_soft_delete_cascades_subtree(session):
    """软删分类应级联软删其所有后代，保证树接口与平铺接口一致"""
    crud = CategoryCrud(session)
    a = await crud.create(name="A", slug="a", parent_id=0, sort=0)
    b = await crud.create(name="B", slug="b", parent_id=a.id, sort=0)
    c = await crud.create(name="C", slug="c", parent_id=b.id, sort=0)
    d = await crud.create(name="D", slug="d", parent_id=0, sort=0)

    assert await crud.soft_delete(b.id) is True

    active_ids = {x.id for x in await crud.get_active_all()}
    assert active_ids == {a.id, d.id}
    c2 = await crud.get_raw_by_id(c.id)
    assert c2.is_deleted is True
    a2 = await crud.get_raw_by_id(a.id)
    assert a2.is_deleted is False


async def test_update_fields(session):
    crud = CategoryCrud(session)
    category = await crud.create(name="旧名", slug="old", parent_id=0, sort=0)
    updated = await crud.update(category.id, name="新名", sort=5)
    assert updated is not None
    assert updated.name == "新名"
    assert updated.slug == "old"
    assert updated.sort == 5


async def test_move_updates_descendants(session):
    crud = CategoryCrud(session)
    a = await crud.create(name="A", slug="a", parent_id=0, sort=0)
    b = await crud.create(name="B", slug="b", parent_id=a.id, sort=0)
    c = await crud.create(name="C", slug="c", parent_id=b.id, sort=0)
    d = await crud.create(name="D", slug="d", parent_id=0, sort=0)

    await crud.update(a.id, parent_id=d.id)

    a2 = await crud.get_raw_by_id(a.id)
    b2 = await crud.get_raw_by_id(b.id)
    c2 = await crud.get_raw_by_id(c.id)
    assert a2.path == f"/{d.id}/{a.id}/"
    assert b2.path == f"/{d.id}/{a.id}/{b.id}/"
    assert c2.path == f"/{d.id}/{a.id}/{b.id}/{c.id}/"
    assert a2.level == 2
    assert b2.level == 3
    assert c2.level == 4


async def test_move_to_descendant_raises(session):
    crud = CategoryCrud(session)
    a = await crud.create(name="A", slug="a", parent_id=0, sort=0)
    b = await crud.create(name="B", slug="b", parent_id=a.id, sort=0)
    with pytest.raises(ValueError):
        await crud.update(a.id, parent_id=b.id)
