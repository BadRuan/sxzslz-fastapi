from typing import Optional
from os import path, makedirs, remove
from pathlib import Path
from sqlmodel.ext.asyncio.session import AsyncSession
from app.settings import upload_dir
from app.model import Image
from app.dao import ImageCrud
from app.model.image import generate_slug
from app.schema import ImageOut, PageResponse
from app.utils import generate_webp_images

class ImageService:
    def __init__(self, session: AsyncSession) -> None:
        self.crud = ImageCrud(session)
        for i in [upload_dir.image_preview, upload_dir.image_raw]:
            if not path.exists(i):
                makedirs(i)
    
    async def list_paginated(self, page: int, page_size: int) -> PageResponse[ImageOut]:
        items, total = await self.crud.list_paginated(page, page_size)
        return PageResponse(
            data=[ImageOut.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
            has_next=page * page_size < total,
        )
    
    async def add(self, filename: str, mime_type: str, content: bytes) -> Optional[Image]:
        suffix = Path(filename).suffix
        slugname = generate_slug() + suffix
        filepath = path.join(upload_dir.image_raw, slugname)
        
        with open(filepath, 'wb') as f:
            f.write(content)
        # 生成预览图和缩略图
        await generate_webp_images(slugname)
        
        await self.crud.add(
            raw_filename=filename,
            slug=slugname,
            mime_type=mime_type,
            size=len(content)
        )
        image = await self.crud.get_by_slug(slugname)
        return image

    async def remove_by_slug(self, slugname: str) -> bool:
        result = await self.crud.remove_by_slug(slugname)
        if result:
            slug, _ = path.splitext(slugname)
            raw_file_path = path.join(upload_dir.image_raw, slugname)
            preview_file_path = path.join(upload_dir.image_preview, slug + ".webp")
            # 两个文件各自独立删除，避免 raw 缺失时预览图泄漏
            if path.isfile(raw_file_path):
                remove(raw_file_path)
            if path.isfile(preview_file_path):
                remove(preview_file_path)
            return True
        return False
    
    async def get_by_slug(self, slugname: str) -> Optional[Image]:
        image: Optional[Image] = await self.crud.get_by_slug(slugname)
        if image is not None:
            await self.crud.record_view(slugname)
            await self.crud.session.refresh(image)
            return image
        else:
            return None