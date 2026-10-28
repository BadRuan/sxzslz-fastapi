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
from app.settings import DOCUMENT_TYPE_LABEL, allow_type, settings, upload_dir
from app.utils import FileTooLargeError, StorageError, ensure_dirs, write_upload_stream


def ensure_document_type(content_type: str | None) -> None:
    """文档 MIME 白名单校验（单文件 / 批量共用同一文案）"""
    received = content_type or "未知"
    if received not in allow_type.document:
        raise ServiceError(
            f"不支持的文件类型「{received}」，仅支持 {DOCUMENT_TYPE_LABEL} 格式"
        )


class DocumentService:
    def __init__(self, session: AsyncSession) -> None:
        self.crud = DocumentCrud(session)

    async def list_paginated(
        self,
        page: int,
        page_size: int,
        sort: DocumentSort = DocumentSort.uploaded_at,
        user_id: int | None = None,
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
        ensure_document_type(mime_type)
        suffix = Path(filename).suffix
        slugname = generate_slug() + suffix
        raw_path = path.join(upload_dir.document, slugname)
        # 只在真正落盘时确保目录存在（exist_ok，避免每个请求都建目录）
        ensure_dirs((upload_dir.document,))
        try:
            size = await write_upload_stream(
                raw_path,
                file,
                max_bytes=settings.MAX_DOCUMENT_SIZE_MB * 1024 * 1024,
            )
        except FileTooLargeError:
            raise ServiceError(
                f"文件大小超过限制（最大 {settings.MAX_DOCUMENT_SIZE_MB}MB）"
            )
        except StorageError as exc:
            raise ServiceError(str(exc)) from exc
        if size == 0:
            remove(raw_path)
            raise ServiceError("文件内容为空")

        await self.crud.add(
            raw_filename=filename,
            slug=slugname,
            mime_type=mime_type,
            size=size,
            user_id=user_id,
        )
        return await self.crud.get_by_slug(slugname)

    async def add_many(self, files: list[UploadFile], user_id: int) -> list[Document]:
        """多文件同时上传：先整批校验类型，再逐个落盘。

        整批原子：任一文件失败 → 抛 ServiceError（400），本批已落盘的文件
        在异常路径立即清理，DB 记录随请求事务回滚，不留半成品。
        """
        if not files:
            raise ServiceError("请至少选择一个文件")
        if len(files) > settings.MAX_BATCH_FILES:
            raise ServiceError(f"单次最多上传 {settings.MAX_BATCH_FILES} 个文件")
        # 先整批校验类型，避免写入部分文件后才发现第 N 个文件类型非法
        for index, file in enumerate(files, start=1):
            try:
                ensure_document_type(file.content_type)
            except ServiceError as exc:
                raise ServiceError(_file_error(index, file, exc)) from exc

        documents: list[Document] = []
        try:
            for index, file in enumerate(files, start=1):
                try:
                    document = await self.add(
                        filename=file.filename or "default_name",
                        mime_type=file.content_type or "",
                        file=file,
                        user_id=user_id,
                    )
                except ServiceError as exc:
                    raise ServiceError(_file_error(index, file, exc)) from exc
                if document is None:
                    raise ServiceError(_file_error(index, file, "上传失败"))
                documents.append(document)
        except Exception:
            # 清理本批已写入的文件与记录；DB 由 get_session 统一 rollback
            for document in documents:
                await self.remove(document.slug)
            raise
        return documents

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


def _file_error(index: int, file: UploadFile, cause: object) -> str:
    """批量上传的逐文件错误文案：定位第几个文件、原始文件名与失败原因"""
    filename = file.filename or "未命名"
    return f"第 {index} 个文件「{filename}」：{cause}"
