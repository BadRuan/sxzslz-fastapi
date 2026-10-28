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
                user_id=1,
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
                user_id=1,
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


async def test_document_list_ordered_by_upload_time_desc(session):
    """文档列表默认按上传时间倒序（最新上传在前）"""
    from datetime import datetime, timedelta

    now = datetime.now()
    ages = [timedelta(hours=1), timedelta(hours=3), timedelta(hours=2)]
    for i, age in enumerate(ages):
        session.add(
            Document(
                raw_filename=f"doc{i}.pdf",
                slug=f"slug{i}.pdf",
                mime_type="application/pdf",
                size_bytes=10,
                user_id=1,
                uploaded_at=now - age,
            )
        )
    await session.flush()

    service = DocumentService(session)
    page = await service.list_paginated(page=1, page_size=10)
    assert [d.slug for d in page.data] == ["slug0.pdf", "slug2.pdf", "slug1.pdf"]


async def test_document_list_sort_by_view(session):
    """sort=view 时按浏览量倒序"""
    from app.schema import DocumentSort

    views = [5, 30, 10]
    for i, v in enumerate(views):
        session.add(
            Document(
                raw_filename=f"doc{i}.pdf",
                slug=f"slug{i}.pdf",
                mime_type="application/pdf",
                size_bytes=10,
                user_id=1,
                view=v,
            )
        )
    await session.flush()

    service = DocumentService(session)
    page = await service.list_paginated(page=1, page_size=10, sort=DocumentSort.view)
    assert [d.slug for d in page.data] == ["slug1.pdf", "slug2.pdf", "slug0.pdf"]


async def test_document_list_sort_api_param(client, session, superadmin_headers):
    """API 层：sort 参数可选，非法值 422；列表需登录（超管看全部）"""
    for i, v in enumerate([5, 30]):
        session.add(
            Document(
                raw_filename=f"doc{i}.pdf",
                slug=f"slug{i}.pdf",
                mime_type="application/pdf",
                size_bytes=10,
                user_id=1,
                view=v,
            )
        )
    await session.flush()

    # 默认：上传时间倒序（同批插入，顺序按 SQLite 返回即可，只校验 200 与结构）
    default_resp = await client.get("/document/", headers=superadmin_headers)
    assert default_resp.status_code == 200

    view_resp = await client.get("/document/?sort=view", headers=superadmin_headers)
    assert view_resp.status_code == 200
    assert [d["slug"] for d in view_resp.json()["data"]] == ["slug1.pdf", "slug0.pdf"]

    assert (
        await client.get("/document/?sort=create_at", headers=superadmin_headers)
    ).status_code == 422
