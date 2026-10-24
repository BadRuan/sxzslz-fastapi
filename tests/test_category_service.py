import pytest

from app.schema import CategoryCreate, CategoryUpdate
from app.service import CategoryService


async def test_create_success(session):
    service = CategoryService(session)
    out = await service.create(CategoryCreate(name="新闻"))
    assert out.id is not None
    assert out.parent_id == 0


async def test_create_child_success(session):
    service = CategoryService(session)
    parent = await service.create(CategoryCreate(name="财务"))
    out = await service.create(CategoryCreate(name="招标", parent_id=parent.id))
    assert out.parent_id == parent.id


async def test_create_third_level_raises(session):
    service = CategoryService(session)
    parent = await service.create(CategoryCreate(name="财务"))
    child = await service.create(CategoryCreate(name="招标", parent_id=parent.id))
    with pytest.raises(ValueError):
        await service.create(CategoryCreate(name="三级", parent_id=child.id))


async def test_create_duplicate_name_allowed(session):
    """分类名允许重名（DB 与应用层均不拦截），不同父级下可同名"""
    service = CategoryService(session)
    top_a = await service.create(CategoryCreate(name="一级A"))
    top_b = await service.create(CategoryCreate(name="一级B"))
    a = await service.create(CategoryCreate(name="其他", parent_id=top_a.id))
    b = await service.create(CategoryCreate(name="其他", parent_id=top_b.id))
    assert a.id != b.id
    assert a.name == b.name == "其他"


async def test_create_reuses_name_after_delete(session):
    """硬删除后的 name 应可被新分类复用"""
    service = CategoryService(session)
    old = await service.create(CategoryCreate(name="旧"))
    await service.delete(old.id)
    out = await service.create(CategoryCreate(name="旧"))
    assert out.name == "旧"


async def test_get_not_found(session):
    service = CategoryService(session)
    assert await service.get(999) is None


async def test_update_and_delete(session):
    service = CategoryService(session)
    out = await service.create(CategoryCreate(name="旧"))
    updated = await service.update(out.id, CategoryUpdate(name="新"))
    assert updated.name == "新"
    assert await service.delete(out.id) is True
    assert await service.get(out.id) is None
