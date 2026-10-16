import pytest
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


async def test_get_not_found(session):
    service = CategoryService(session)
    assert await service.get(999) is None


async def test_update_and_delete(session):
    service = CategoryService(session)
    out = await service.create(CategoryCreate(name="旧", slug="old"))
    updated = await service.update(out.id, CategoryUpdate(name="新"))
    assert updated.name == "新"
    assert updated.slug == "old"
    assert await service.delete(out.id) is True
    assert await service.get(out.id) is None
