from typing import List, Optional
from sqlmodel import select, update, func, desc
from sqlmodel.ext.asyncio.session import AsyncSession
from app.model import Document, PageResponse


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
        items: List[Image] = list(results.all()) # type: ignore
        return PageResponse(
            total=total_count,
            page=page,
            page_size=page_size,
            items=items
        )
    
    async def get_by_slug(self, slugname: str) -> Optional[Document]:
        stmt = select(Document).where(Document.slug == slugname)
        result = await self.session.exec(stmt)
        document = result.first()
        return document
    
    
    async def add(self, raw_filename: str, slug: str, mime_type: str, size: int) -> Optional[Document]:
        image_record = Document(
            raw_filename=raw_filename,
            slug=slug,
            mime_type=mime_type,
            size_bytes=size
        )
        item = self.session.add(image_record) 
        await self.session.commit()
        return item
    
    async def recoder_view(self, slugname: str) -> None:
        stmt = (
            update(Document)
            .where(Document.slug == slugname) # type: ignore
            .values({Document.view: Document.view + 1})
        )
        await self.session.exec(stmt)
        await self.session.commit()
    
    async def remove_by_slug(self, slugname: str) -> bool:
        image = await self.get_by_slug(slugname)
        if image is not None:
            await self.session.delete(image)
            await self.session.commit()
            return True
        return False
