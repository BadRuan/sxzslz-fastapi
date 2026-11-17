from os import path, remove
from typing import Optional

from fastapi import UploadFile
from PIL import UnidentifiedImageError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.dao import ImageCrud
from app.errors import ServiceError
from app.model import Image
from app.model.image import generate_slug
from app.schema import ImageOut, PageResponse, page_response
from app.settings import IMAGE_TYPE_LABEL, allow_type, settings, upload_dir
from app.service.file import BaseFileService, _UploadResult
from app.utils import generate_webp_images, storage_error_from


def ensure_image_type(content_type: str | None) -> None:
    """图片 MIME 白名单校验（单文件 / 批量共用同一文案）"""
    received = content_type or "未知"
    if received not in allow_type.image:
        raise ServiceError(
            f"不支持的图片类型「{received}」，仅支持 {IMAGE_TYPE_LABEL} 格式"
        )


class ImageService(BaseFileService[Image]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(
            ImageCrud(session),
            slug_factory=generate_slug,
            max_bytes=settings.MAX_IMAGE_SIZE_MB * 1024 * 1024,
            size_limit_msg=f"图片大小超过限制（最大 {settings.MAX_IMAGE_SIZE_MB}MB）",
            dirs=(upload_dir.image_raw, upload_dir.image_preview),
        )

    def ensure_type(self, content_type: str | None) -> None:
        ensure_image_type(content_type)

    async def post_upload(
        self, slugname: str, raw_path: str
    ) -> _UploadResult:
        # 计算原图 MD5，用于内容去重（在生成预览前，避免重复工作）
        md5_value = _md5_file(raw_path)

        # 已存在相同内容的图片：不重复落盘，复用已有记录
        existing = await self.crud.get_by_md5(md5_value)
        if existing is not None:
            if path.isfile(raw_path):
                remove(raw_path)
            return _UploadResult(action="dedup_hit", record=existing)

        # 生成预览图和缩略图（PIL 在线程池执行）；失败清理原图，不残留半成品
        try:
            await generate_webp_images(slugname)
        except UnidentifiedImageError:
            remove(raw_path)
            raise ServiceError(
                "不是有效的图片文件（内容可能已损坏或格式不符）"
            ) from None
        except OSError as exc:
            remove(raw_path)
            raise ServiceError(storage_error_from(exc)) from exc
        except Exception as exc:
            remove(raw_path)
            raise ServiceError("图片处理失败，请更换图片后重试") from exc

        return _UploadResult(action="proceed", md5=md5_value)

    def remove_file(self, slugname: str) -> None:
        # 先交给基类删除原图，再独立删除预览 webp
        super().remove_file(slugname)
        slug, _ = path.splitext(slugname)
        preview_file_path = path.join(upload_dir.image_preview, slug + ".webp")
        if path.isfile(preview_file_path):
            remove(preview_file_path)

    async def list_paginated(
        self, page: int, page_size: int, user_id: Optional[int] = None
    ) -> PageResponse[ImageOut]:
        items, total = await self.crud.list_paginated(page, page_size, user_id=user_id)
        return page_response(
            [ImageOut.model_validate(i) for i in items], total, page, page_size
        )

    async def add(
        self, filename: str, mime_type: str, file: UploadFile, user_id: int
    ) -> Optional[Image]:
        return await super().add(filename, mime_type, file, user_id)

    async def add_many(self, files: list[UploadFile], user_id: int) -> list[Image]:
        return await super().add_many(files, user_id)

    async def find_by_slug(self, slugname: str) -> Optional[Image]:
        """只读查询，不自增 view（权限校验 / 改名前定位用）"""
        return await self.crud.get_by_slug(slugname)

    async def remove_by_slug(self, slugname: str) -> bool:
        return await self.remove(slugname)

    async def rename(self, slugname: str, raw_filename: str) -> Optional[Image]:
        """改展示名；记录不存在返回 None"""
        return await self.crud.update_raw_filename(slugname, raw_filename)

    async def get_by_slug(self, slugname: str) -> Optional[Image]:
        image: Optional[Image] = await self.crud.get_by_slug(slugname)
        if image is None:
            return None
        # 原子自增并用 RETURNING 的新计数就地更新，省掉一次 refresh 查询
        new_view = await self.crud.record_view(slugname)
        if new_view is not None:
            image.view = new_view
        return image


def _md5_file(filepath: str) -> str:
    import hashlib

    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
