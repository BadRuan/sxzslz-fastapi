from os import path, remove
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from sqlmodel.ext.asyncio.session import AsyncSession

from app.dao import ImageCrud
from app.errors import ServiceError
from app.model import Image
from app.model.image import generate_slug
from app.schema import PageResponse, ImageOut, page_response
from app.settings import settings, upload_dir
from app.utils import (
    FileTooLargeError,
    ensure_dirs,
    generate_webp_images,
    write_upload_stream,
)


class ImageService:
    def __init__(self, session: AsyncSession) -> None:
        self.crud = ImageCrud(session)

    async def list_paginated(self, page: int, page_size: int) -> PageResponse[ImageOut]:
        items, total = await self.crud.list_paginated(page, page_size)
        return page_response(
            [ImageOut.model_validate(i) for i in items], total, page, page_size
        )

    async def add(
        self, filename: str, mime_type: str, file: UploadFile, user_id: int
    ) -> Optional[Image]:
        suffix = Path(filename).suffix
        slugname = generate_slug() + suffix
        # 只在真正落盘时确保目录存在（exist_ok，避免每个请求都建目录）
        ensure_dirs((upload_dir.image_raw, upload_dir.image_preview))
        raw_path = path.join(upload_dir.image_raw, slugname)
        try:
            size = await write_upload_stream(
                raw_path, file, max_bytes=settings.MAX_IMAGE_SIZE_MB * 1024 * 1024
            )
        except FileTooLargeError:
            raise ServiceError(f"图片大小超过限制（最大 {settings.MAX_IMAGE_SIZE_MB}MB）")
        if size == 0:
            remove(raw_path)
            raise ServiceError("文件内容为空")

        # 生成预览图和缩略图（PIL 在线程池执行）
        await generate_webp_images(slugname)

        await self.crud.add(
            raw_filename=filename,
            slug=slugname,
            mime_type=mime_type,
            size=size,
            user_id=user_id,
        )
        return await self.crud.get_by_slug(slugname)

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
        if image is None:
            return None
        # 原子自增并用 RETURNING 的新计数就地更新，省掉一次 refresh 查询
        new_view = await self.crud.record_view(slugname)
        if new_view is not None:
            image.view = new_view
        return image
