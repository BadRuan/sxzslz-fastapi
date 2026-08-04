from typing import List, Optional
from sqlmodel import select, update, func, desc
from sqlmodel.ext.asyncio.session import AsyncSession
from app.model import Image
from app.schema import PageResponse


class ImageCrud:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        
    async def list_paginated(self, page: int, page_size: int) -> PageResponse[Image]:
        count_stmt = select(func.count()).select_from(Image)
        total = await self.session.exec(count_stmt)
        total_count: int = total.one()
        
        offset = (page - 1) * page_size
        
        data_stmt = (
            select(Image)
            .offset(offset)
            .limit(page_size)
            .order_by(desc(Image.id))
        )
        results = await self.session.exec(data_stmt)
        items: List[Image] = list(results.all()) # type: ignore
        return PageResponse(
            total=total_count,
            page=page,
            has_next=False,
            page_size=page_size,
            data=items
        )
    
    async def get_by_slug(self, slugname: str) -> Optional[Image]:
        stmt = select(Image).where(Image.slug == slugname)
        result = await self.session.exec(stmt)
        image = result.first()
        return image
    
    
    async def add(self, raw_filename: str, slug: str, mime_type: str, size: int) -> Optional[Image]:
        image_record = Image(
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
            update(Image)
            .where(Image.slug == slugname) # type: ignore
            .values({Image.view: Image.view + 1})
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

    async def get_total_count(self) -> int:
        return (await self.session.scalar(
            func.count(Image.id)  # type: ignore[arg-type]
        )) or 0

    async def get_total_view(self) -> int:
        return (await self.session.scalar(
                    func.sum(Image.view)  # type: ignore[arg-type]
                )) or 0