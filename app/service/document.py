from os import path, remove
from typing import Optional

from fastapi import UploadFile
from sqlmodel.ext.asyncio.session import AsyncSession

from app.dao import DocumentCrud
from app.errors import ServiceError
from app.model import Document
from app.model.document import generate_slug
from app.schema import DocumentOut, DocumentSort, PageResponse, page_response
from app.settings import DOCUMENT_TYPE_LABEL, allow_type, settings, upload_dir
from app.service.file import BaseFileService
from app.utils import storage_error_from


def ensure_document_type(content_type: str | None) -> None:
    """文档 MIME 白名单校验（单文件 / 批量共用同一文案）"""
    received = content_type or "未知"
    if received not in allow_type.document:
        raise ServiceError(
            f"不支持的文件类型「{received}」，仅支持 {DOCUMENT_TYPE_LABEL} 格式"
        )


class DocumentService(BaseFileService[Document]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(
            DocumentCrud(session),
            slug_factory=generate_slug,
            max_bytes=settings.MAX_DOCUMENT_SIZE_MB * 1024 * 1024,
            size_limit_msg=f"文件大小超过限制（最大 {settings.MAX_DOCUMENT_SIZE_MB}MB）",
            dirs=(upload_dir.document,),
        )

    def ensure_type(self, content_type: str | None) -> None:
        ensure_document_type(content_type)

    async def list_paginated(
        self,
        page: int,
        page_size: int,
        sort: DocumentSort = DocumentSort.uploaded_at,
        user_id: Optional[int] = None,
    ) -> PageResponse[DocumentOut]:
        items, total = await self.crud.list_paginated(
            page, page_size, order_by_field=sort.value, user_id=user_id
        )
        return page_response(
            [DocumentOut.model_validate(i) for i in items], total, page, page_size
        )

    async def add(
        self, filename: str, mime_type: str, file: UploadFile, user_id: int
    ) -> Optional[Document]:
        return await super().add(filename, mime_type, file, user_id)

    async def add_many(self, files: list[UploadFile], user_id: int) -> list[Document]:
        return await super().add_many(files, user_id)

    async def find_by_slug(self, slugname: str) -> Optional[Document]:
        """只读查询，不自增 view（权限校验 / 改名前定位用）"""
        return await self.crud.get_by_slug(slugname)

    async def remove(self, slugname: str) -> bool:
        """删除 DB 记录并清理磁盘文件；记录不存在返回 False"""
        return await super().remove(slugname)

    async def rename(self, slugname: str, raw_filename: str) -> Optional[Document]:
        """改展示名；记录不存在返回 None"""
        return await self.crud.update_raw_filename(slugname, raw_filename)

    async def get_by_slug(self, slugname: str) -> Optional[Document]:
        document: Optional[Document] = await self.crud.get_by_slug(slugname)
        if document is None:
            return None
        # 原子自增并用 RETURNING 的新计数就地更新，省掉一次 refresh 查询
        new_view = await self.crud.record_view(slugname)
        if new_view is not None:
            document.view = new_view
        return document
