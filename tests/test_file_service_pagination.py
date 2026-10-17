from app.dao import DocumentCrud, ImageCrud
from app.model import Document, Image
from app.service import DocumentService, ImageService


async def _seed_images(session, n: int) -> None:
    for i in range(n):
        session.add(
            Image(
                raw_filename=f"img{i}.png",
                slug=f"slug{i}.png",
                mime_type="image/png",
                size_bytes=10,
            )
        )
    await session.flush()


async def _seed_documents(session, n: int) -> None:
    for i in range(n):
        session.add(
            Document(
                raw_filename=f"doc{i}.pdf",
                slug=f"slug{i}.pdf",
                mime_type="application/pdf",
                size_bytes=10,
            )
        )
    await session.flush()


async def test_image_list_has_next_true_when_more_pages(session):
    await _seed_images(session, 3)
    service = ImageService(session)
    page = await service.list_paginated(page=1, page_size=2)
    assert page.has_next is True
    assert page.total == 3
    assert len(page.data) == 2


async def test_image_list_has_next_false_on_last_page(session):
    await _seed_images(session, 3)
    service = ImageService(session)
    page = await service.list_paginated(page=2, page_size=2)
    assert page.has_next is False
    assert len(page.data) == 1


async def test_document_list_has_next_empty(session):
    service = DocumentService(session)
    page = await service.list_paginated(page=1, page_size=10)
    assert page.has_next is False
    assert page.total == 0
    assert page.data == []


async def test_document_list_has_next_boundary_exact_multiple(session):
    await _seed_documents(session, 4)
    service = DocumentService(session)
    page = await service.list_paginated(page=2, page_size=2)
    assert page.has_next is False
    assert page.total == 4
