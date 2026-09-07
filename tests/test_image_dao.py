import pytest
from sqlmodel.ext.asyncio.session import AsyncSession
from app.dao import ImageCrud


@pytest.fixture
def image_crud(session: AsyncSession):
    return ImageCrud(session)


async def test_add_image(session: AsyncSession, image_crud: ImageCrud):
    img = await image_crud.add("test.jpg", "abc123", "image/jpeg", 1024)
    assert img.id is not None
    assert img.raw_filename == "test.jpg"
    assert img.slug == "abc123"
    assert img.mime_type == "image/jpeg"
    assert img.size_bytes == 1024
    assert img.view == 0


async def test_get_by_slug(session: AsyncSession, image_crud: ImageCrud):
    await image_crud.add("test.jpg", "slug1", "image/jpeg", 1024)
    result = await image_crud.get_by_slug("slug1")
    assert result is not None
    assert result.raw_filename == "test.jpg"


async def test_get_by_slug_not_found(session: AsyncSession, image_crud: ImageCrud):
    result = await image_crud.get_by_slug("nonexistent")
    assert result is None


async def test_list_paginated(session: AsyncSession, image_crud: ImageCrud):
    for i in range(5):
        await image_crud.add(f"img{i}.jpg", f"slug{i}", "image/jpeg", 100)

    page = await image_crud.list_paginated(page=1, page_size=2)
    assert page.total == 5
    assert page.page == 1
    assert page.page_size == 2
    assert len(page.data) == 2


async def test_list_paginated_second_page(session: AsyncSession, image_crud: ImageCrud):
    for i in range(5):
        await image_crud.add(f"img{i}.jpg", f"slug{i}", "image/jpeg", 100)

    page = await image_crud.list_paginated(page=2, page_size=2)
    assert len(page.data) == 2
    assert page.page == 2


async def test_record_view(session: AsyncSession, image_crud: ImageCrud):
    await image_crud.add("test.jpg", "slug1", "image/jpeg", 1024)
    await image_crud.record_view("slug1")
    await session.flush()

    img = await image_crud.get_by_slug("slug1")
    assert img.view == 1


async def test_remove_by_slug(session: AsyncSession, image_crud: ImageCrud):
    await image_crud.add("test.jpg", "slug1", "image/jpeg", 1024)
    removed = await image_crud.remove_by_slug("slug1")
    assert removed is True

    result = await image_crud.get_by_slug("slug1")
    assert result is None


async def test_remove_by_slug_not_found(session: AsyncSession, image_crud: ImageCrud):
    removed = await image_crud.remove_by_slug("nonexistent")
    assert removed is False


async def test_get_total_count(session: AsyncSession, image_crud: ImageCrud):
    for i in range(3):
        await image_crud.add(f"img{i}.jpg", f"slug{i}", "image/jpeg", 100)
    count = await image_crud.get_total_count()
    assert count == 3


async def test_get_total_view(session: AsyncSession, image_crud: ImageCrud):
    await image_crud.add("a.jpg", "s1", "image/jpeg", 100)
    await image_crud.add("b.jpg", "s2", "image/jpeg", 100)
    await image_crud.record_view("s1")
    await image_crud.record_view("s1")
    await image_crud.record_view("s2")
    await session.flush()

    total = await image_crud.get_total_view()
    assert total == 3
