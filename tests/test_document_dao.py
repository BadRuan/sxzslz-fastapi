import pytest
from sqlmodel.ext.asyncio.session import AsyncSession
from app.dao import DocumentCrud


@pytest.fixture
def doc_crud(session: AsyncSession):
    return DocumentCrud(session)


async def test_add_document(session: AsyncSession, doc_crud: DocumentCrud):
    doc = await doc_crud.add("report.pdf", "doc-slug", "application/pdf", 2048)
    assert doc.id is not None
    assert doc.raw_filename == "report.pdf"
    assert doc.slug == "doc-slug"
    assert doc.mime_type == "application/pdf"
    assert doc.size_bytes == 2048
    assert doc.view == 0


async def test_get_by_slug(session: AsyncSession, doc_crud: DocumentCrud):
    await doc_crud.add("report.pdf", "slug1", "application/pdf", 2048)
    result = await doc_crud.get_by_slug("slug1")
    assert result is not None
    assert result.raw_filename == "report.pdf"


async def test_get_by_slug_not_found(session: AsyncSession, doc_crud: DocumentCrud):
    result = await doc_crud.get_by_slug("nonexistent")
    assert result is None


async def test_list_paginated(session: AsyncSession, doc_crud: DocumentCrud):
    for i in range(5):
        await doc_crud.add(f"doc{i}.pdf", f"slug{i}", "application/pdf", 100)

    page = await doc_crud.list_paginated(page=1, page_size=2)
    assert page.total == 5
    assert page.page == 1
    assert page.page_size == 2
    assert len(page.data) == 2


async def test_record_view(session: AsyncSession, doc_crud: DocumentCrud):
    await doc_crud.add("report.pdf", "slug1", "application/pdf", 2048)
    await doc_crud.record_view("slug1")
    await session.flush()

    doc = await doc_crud.get_by_slug("slug1")
    assert doc.view == 1


async def test_remove_by_slug(session: AsyncSession, doc_crud: DocumentCrud):
    await doc_crud.add("report.pdf", "slug1", "application/pdf", 2048)
    removed = await doc_crud.remove_by_slug("slug1")
    assert removed is True

    result = await doc_crud.get_by_slug("slug1")
    assert result is None


async def test_remove_by_slug_not_found(session: AsyncSession, doc_crud: DocumentCrud):
    removed = await doc_crud.remove_by_slug("nonexistent")
    assert removed is False


async def test_get_total_count(session: AsyncSession, doc_crud: DocumentCrud):
    for i in range(3):
        await doc_crud.add(f"doc{i}.pdf", f"slug{i}", "application/pdf", 100)
    count = await doc_crud.get_total_count()
    assert count == 3


async def test_get_download_count(session: AsyncSession, doc_crud: DocumentCrud):
    """DAO 使用 count(Document.view) 统计的是非空记录数，不是 view 的总和"""
    await doc_crud.add("a.pdf", "s1", "application/pdf", 100)
    await doc_crud.add("b.pdf", "s2", "application/pdf", 100)
    await doc_crud.record_view("s1")
    await doc_crud.record_view("s1")
    await doc_crud.record_view("s2")
    await session.flush()

    count = await doc_crud.get_download_count()
    assert count == 2  # count(Document.view) 统计记录数，非 view 总和
