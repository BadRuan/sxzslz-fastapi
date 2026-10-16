from typing import List, Optional
from sqlmodel import select, update, func, desc
from sqlmodel.ext.asyncio.session import AsyncSession
from app.model import Document
from app.schema import PageResponse


class DocumentCrud:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_paginated(self, page: int, page_size: int) -> PageResponse[Document]:
        count_stmt = select(func.count()).select_from(Document)
        total = await self.session.exec(count_stmt)
        total_count: int = total.one()

        offset = (page - 1) * page_size

        data_stmt = (
            select(Document)
            .offset(offset)
            .limit(page_size)
            .order_by(desc(Document.view))
        )
        results = await self.session.exec(data_stmt)
        items: List[Document] = list(results.all())
        return PageResponse(
            total=total_count,
            page=page,
            has_next=False,
            page_size=page_size,
            data=items
        )

    async def get_by_slug(self, slugname: str) -> Optional[Document]:
        stmt = select(Document).where(Document.slug == slugname)
        result = await self.session.exec(stmt)
        return result.first()

    async def add(self, raw_filename: str, slug: str, mime_type: str, size: int) -> Document:
        document_record = Document(
            raw_filename=raw_filename,
            slug=slug,
            mime_type=mime_type,
            size_bytes=size
        )
        self.session.add(document_record)
        await self.session.flush()
        return document_record

    async def get_view(self, slugname: str) -> None:
        stmt = (
            update(Document)
            .where(Document.slug == slugname) # type: ignore
            .values(view=Document.view + 1)
        )
        await self.session.exec(stmt)

    async def remove_by_slug(self, slugname: str) -> bool:
        document = await self.get_by_slug(slugname)
        if document is not None:
            await self.session.delete(document)
            return True
        return False

    async def get_count(self) -> int:
        return (await self.session.scalar(
            func.count(Document.id) # type: ignore
        )) or 0

    async def get_download(self) -> int:
        return (await self.session.scalar(
            func.count(Document.view) # type: ignore
        )) or 0
