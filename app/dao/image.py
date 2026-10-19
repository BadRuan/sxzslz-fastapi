from typing import List, Optional, Tuple
from sqlmodel import desc, func, select, update
from sqlmodel.ext.asyncio.session import AsyncSession
from app.model import Image


class ImageCrud:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_paginated(self, page: int, page_size: int) -> Tuple[List[Image], int]:
        count_stmt = select(func.count()).select_from(Image)
        total = await self.session.exec(count_stmt)
        total_count: int = total.one()

        offset = (page - 1) * page_size

        data_stmt = (
            select(Image).offset(offset).limit(page_size).order_by(desc(Image.id))
        )
        results = await self.session.exec(data_stmt)
        items: List[Image] = list(results.all())
        return items, total_count

    async def get_by_slug(self, slugname: str) -> Optional[Image]:
        stmt = select(Image).where(Image.slug == slugname)
        result = await self.session.exec(stmt)
        return result.first()

    async def add(
        self, raw_filename: str, slug: str, mime_type: str, size: int
    ) -> Image:
        image_record = Image(
            raw_filename=raw_filename,
            slug=slug,
            mime_type=mime_type,
            size_bytes=size,
        )
        self.session.add(image_record)
        await self.session.flush()
        return image_record

    async def record_view(self, slugname: str) -> None:
        stmt = (
            update(Image)
            .where(Image.slug == slugname)  # type: ignore
            .values(view=Image.view + 1)
        )
        await self.session.exec(stmt)

    async def remove_by_slug(self, slugname: str) -> bool:
        image = await self.get_by_slug(slugname)
        if image is not None:
            await self.session.delete(image)
            return True
        return False
