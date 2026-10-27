from os import path, remove
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from sqlmodel.ext.asyncio.session import AsyncSession

from app.dao import DocumentCrud
from app.errors import ServiceError
from app.model import Document
from app.model.document import generate_slug
from app.schema import DocumentOut, DocumentSort, PageResponse, page_response
from app.settings import settings, upload_dir
from app.utils import FileTooLargeError, ensure_dirs, write_upload_stream


class DocumentService:
    def __init__(self, session: AsyncSession) -> None:
        self.crud = DocumentCrud(session)

    async def list_paginated(
        self,
        page: int,
        page_size: int,
        sort: DocumentSort = DocumentSort.uploaded_at,
    ) -> PageResponse[DocumentOut]:
        items, total = await self.crud.list_paginated(
            page, page_size, order_by_field=sort.value
        )
        return page_response(
            [DocumentOut.model_validate(i) for i in items], total, page, page_size
        )

    async def add(
        self, filename: str, mime_type: str, file: UploadFile, user_id: int
    ) -> Optional[Document]:
        suffix = Path(filename).suffix
        slugname = generate_slug() + suffix
        # 只在真正落盘时确保目录存在（exist_ok，避免每个请求都建目录）
        ensure_dirs((upload_dir.document,))
        try:
            size = await write_upload_stream(
                path.join(upload_dir.document, slugname),
                file,
                max_bytes=settings.MAX_DOCUMENT_SIZE_MB * 1024 * 1024,
            )
        except FileTooLargeError:
            raise ServiceError(
                f"文件大小超过限制（最大 {settings.MAX_DOCUMENT_SIZE_MB}MB）"
            )
        if size == 0:
            remove(path.join(upload_dir.document, slugname))
            raise ServiceError("文件内容为空")

        await self.crud.add(
            raw_filename=filename,
            slug=slugname,
            mime_type=mime_type,
            size=size,
            user_id=user_id,
        )
        return await self.crud.get_by_slug(slugname)

    async def find_by_slug(self, slugname: str) -> Optional[Document]:
        """只读查询，不自增 view（权限校验 / 改名前定位用）"""
        return await self.crud.get_by_slug(slugname)

    async def rename(self, slugname: str, raw_filename: str) -> Optional[Document]:
        """改展示名；记录不存在返回 None"""
        return await self.crud.update_raw_filename(slugname, raw_filename)

    async def remove(self, slugname: str) -> bool:
        """删除 DB 记录并清理磁盘文件；记录不存在返回 False"""
        result = await self.crud.remove_by_slug(slugname)
        if result:
            file_path = path.join(upload_dir.document, slugname)
            if path.isfile(file_path):
                remove(file_path)
            return True
        return False

    async def get_by_slug(self, slugname: str) -> Optional[Document]:
        document: Optional[Document] = await self.crud.get_by_slug(slugname)
        if document is None:
            return None
        # 原子自增并用 RETURNING 的新计数就地更新，省掉一次 refresh 查询
        new_view = await self.crud.record_view(slugname)
        if new_view is not None:
            document.view = new_view
        return document
