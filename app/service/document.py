from os import path, remove
from pathlib import Path
from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.dao import DocumentCrud
from app.model import Document
from app.model.document import generate_slug
from app.schema import DocumentOut, DocumentSort, PageResponse, page_response
from app.settings import upload_dir
from app.utils import ensure_dirs, write_bytes_async


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
        self, filename: str, mime_type: str, content: bytes, user_id: int
    ) -> Optional[Document]:
        suffix = Path(filename).suffix
        slugname = generate_slug() + suffix
        # 只在真正落盘时确保目录存在（exist_ok，避免每个请求都建目录）
        ensure_dirs((upload_dir.document,))
        await write_bytes_async(path.join(upload_dir.document, slugname), content)

        await self.crud.add(
            raw_filename=filename,
            slug=slugname,
            mime_type=mime_type,
            size=len(content),
            user_id=user_id,
        )
        return await self.crud.get_by_slug(slugname)

    async def remove_by_slug(self, slugname: str) -> bool:
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
