from os import path, remove
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from PIL import UnidentifiedImageError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.dao import ImageCrud
from app.errors import ServiceError
from app.model import Image
from app.model.image import generate_slug
from app.schema import PageResponse, ImageOut, page_response
from app.settings import IMAGE_TYPE_LABEL, allow_type, settings, upload_dir
from app.utils import (
    FileTooLargeError,
    StorageError,
    ensure_dirs,
    generate_webp_images,
    storage_error_from,
    write_upload_stream,
)


def ensure_image_type(content_type: str | None) -> None:
    """图片 MIME 白名单校验（单文件 / 批量共用同一文案）"""
    received = content_type or "未知"
    if received not in allow_type.image:
        raise ServiceError(
            f"不支持的图片类型「{received}」，仅支持 {IMAGE_TYPE_LABEL} 格式"
        )


class ImageService:
    def __init__(self, session: AsyncSession) -> None:
        self.crud = ImageCrud(session)

    async def list_paginated(
        self, page: int, page_size: int, user_id: int | None = None
    ) -> PageResponse[ImageOut]:
        items, total = await self.crud.list_paginated(page, page_size, user_id=user_id)
        return page_response(
            [ImageOut.model_validate(i) for i in items], total, page, page_size
        )

    async def add(
        self, filename: str, mime_type: str, file: UploadFile, user_id: int
    ) -> Optional[Image]:
        ensure_image_type(mime_type)
        suffix = Path(filename).suffix
        slugname = generate_slug() + suffix
        raw_path = path.join(upload_dir.image_raw, slugname)
        # 只在真正落盘时确保目录存在（exist_ok，避免每个请求都建目录）
        ensure_dirs((upload_dir.image_raw, upload_dir.image_preview))
        try:
            size = await write_upload_stream(
                raw_path, file, max_bytes=settings.MAX_IMAGE_SIZE_MB * 1024 * 1024
            )
        except FileTooLargeError:
            raise ServiceError(f"图片大小超过限制（最大 {settings.MAX_IMAGE_SIZE_MB}MB）")
        except StorageError as exc:
            raise ServiceError(str(exc)) from exc
        if size == 0:
            remove(raw_path)
            raise ServiceError("文件内容为空")

        # 生成预览图和缩略图（PIL 在线程池执行）；失败清理原图，不残留半成品
        try:
            await generate_webp_images(slugname)
        except UnidentifiedImageError:
            remove(raw_path)
            raise ServiceError("不是有效的图片文件（内容可能已损坏或格式不符）") from None
        except OSError as exc:
            remove(raw_path)
            raise ServiceError(storage_error_from(exc)) from exc
        except Exception as exc:
            remove(raw_path)
            raise ServiceError("图片处理失败，请更换图片后重试") from exc

        await self.crud.add(
            raw_filename=filename,
            slug=slugname,
            mime_type=mime_type,
            size=size,
            user_id=user_id,
        )
        return await self.crud.get_by_slug(slugname)

    async def add_many(self, files: list[UploadFile], user_id: int) -> list[Image]:
        """多图同时上传：先整批校验类型，再逐个落盘。

        整批原子：任一文件失败 → 抛 ServiceError（400），本批已落盘的图片文件
        在异常路径立即清理，DB 记录随请求事务回滚，不留半成品。
        """
        if not files:
            raise ServiceError("请至少选择一个文件")
        if len(files) > settings.MAX_BATCH_FILES:
            raise ServiceError(f"单次最多上传 {settings.MAX_BATCH_FILES} 个文件")
        # 先整批校验类型，避免写入部分文件后才发现第 N 个文件类型非法
        for index, file in enumerate(files, start=1):
            try:
                ensure_image_type(file.content_type)
            except ServiceError as exc:
                raise ServiceError(_file_error(index, file, exc)) from exc

        images: list[Image] = []
        try:
            for index, file in enumerate(files, start=1):
                try:
                    image = await self.add(
                        filename=file.filename or "default_name",
                        mime_type=file.content_type or "",
                        file=file,
                        user_id=user_id,
                    )
                except ServiceError as exc:
                    raise ServiceError(_file_error(index, file, exc)) from exc
                if image is None:
                    raise ServiceError(_file_error(index, file, "上传失败"))
                images.append(image)
        except Exception:
            # 清理本批已写入的文件与记录；DB 由 get_session 统一 rollback
            for image in images:
                await self.remove_by_slug(image.slug)
            raise
        return images

    async def find_by_slug(self, slugname: str) -> Optional[Image]:
        """只读查询，不自增 view（权限校验 / 改名前定位用）"""
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


def _file_error(index: int, file: UploadFile, cause: object) -> str:
    """批量上传的逐文件错误文案：定位第几个文件、原始文件名与失败原因"""
    filename = file.filename or "未命名"
    return f"第 {index} 个文件「{filename}」：{cause}"
