import pytest
from sqlalchemy.exc import IntegrityError

from app.dao import CategoryCrud
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


async def test_create_duplicate_name_raises(session):
    service = CategoryService(session)
    await service.create(CategoryCreate(name="新闻"))
    with pytest.raises(ValueError):
        await service.create(CategoryCreate(name="新闻"))


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


async def test_create_race_duplicate_converted_to_valueerror(session, monkeypatch):
    """校验通过后并发插入重复 name 时，IntegrityError 应转为 ValueError（→400）"""
    service = CategoryService(session)
    await service.create(CategoryCreate(name="竞态"))

    async def no_match(self, name):
        return None

    monkeypatch.setattr(CategoryCrud, "get_by_name", no_match)

    with pytest.raises(ValueError):
        await service.create(CategoryCreate(name="竞态"))


async def test_db_rejects_duplicate_name(session):
    """守护：分类 name 在 DB 层仍受唯一性保护（防止 schema 改动丢失约束）"""
    crud = CategoryCrud(session)
    await crud.create(name="唯一", parent_id=0, sort=0)
    with pytest.raises(IntegrityError):
        await crud.create(name="唯一", parent_id=0, sort=0)


async def test_update_and_delete(session):
    service = CategoryService(session)
    out = await service.create(CategoryCreate(name="旧"))
    updated = await service.update(out.id, CategoryUpdate(name="新"))
    assert updated.name == "新"
    assert await service.delete(out.id) is True
    assert await service.get(out.id) is None
