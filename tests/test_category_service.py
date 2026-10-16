import pytest
from sqlalchemy.exc import IntegrityError
from app.dao import CategoryCrud
from app.service import CategoryService
from app.schema import CategoryCreate, CategoryUpdate


async def test_create_success(session):
    service = CategoryService(session)
    out = await service.create(CategoryCreate(name="新闻", slug="xinwen"))
    assert out.id is not None
    assert out.parent_id == 0
    assert out.level == 1


async def test_create_duplicate_name_raises(session):
    service = CategoryService(session)
    await service.create(CategoryCreate(name="新闻", slug="xinwen"))
    with pytest.raises(ValueError):
        await service.create(CategoryCreate(name="新闻", slug="xinwen2"))


async def test_create_duplicate_slug_raises(session):
    service = CategoryService(session)
    await service.create(CategoryCreate(name="新闻", slug="xinwen"))
    with pytest.raises(ValueError):
        await service.create(CategoryCreate(name="新闻2", slug="xinwen"))


async def test_create_reuses_soft_deleted_name_and_slug(session):
    """软删后的 name/slug 应可被新分类复用"""
    service = CategoryService(session)
    old = await service.create(CategoryCreate(name="旧", slug="old"))
    await service.delete(old.id)
    out = await service.create(CategoryCreate(name="旧", slug="old"))
    assert out.id != old.id


async def test_get_not_found(session):
    service = CategoryService(session)
    assert await service.get(999) is None


async def test_create_race_duplicate_converted_to_valueerror(session, monkeypatch):
    """校验通过后并发插入重复 name 时，IntegrityError 应转为 ValueError（→400）"""
    service = CategoryService(session)
    await service.create(CategoryCreate(name="竞态", slug="race1"))

    async def no_match(self, name_or_slug):
        return None

    monkeypatch.setattr(CategoryCrud, "get_by_name", no_match)
    monkeypatch.setattr(CategoryCrud, "get_by_slug", no_match)

    with pytest.raises(ValueError):
        await service.create(CategoryCreate(name="竞态", slug="race2"))


async def test_db_rejects_duplicate_active_name(session):
    """守护：活跃分类的 name 在 DB 层仍受唯一性保护（防止 schema 改动丢失约束）"""
    crud = CategoryCrud(session)
    await crud.create(name="唯一", slug="u1", parent_id=0, sort=0)
    with pytest.raises(IntegrityError):
        await crud.create(name="唯一", slug="u2", parent_id=0, sort=0)


async def test_update_and_delete(session):
    service = CategoryService(session)
    out = await service.create(CategoryCreate(name="旧", slug="old"))
    updated = await service.update(out.id, CategoryUpdate(name="新"))
    assert updated.name == "新"
    assert updated.slug == "old"
    assert await service.delete(out.id) is True
    assert await service.get(out.id) is None
