from typing import Optional
from os import path, makedirs, remove
from pathlib import Path
from sqlmodel.ext.asyncio.session import AsyncSession
from app.settings import upload_dir
from app.schema import PageResponse
from app.model import Document
from app.dao import DocumentCrud


class DocumentService:
    def __init__(self, session: AsyncSession) -> None:
        self.crud = DocumentCrud(session)
        if not path.exists(upload_dir.document):
            makedirs(upload_dir.document)
    
    async def list_paginated(self, page: int, page_size: int) -> PageResponse[Document]:
        return await self.crud.list_paginated(page, page_size)
    
    async def add(self, filename: str, mime_type: str, content: bytes) -> Optional[Document]:
        suffiex = Path(filename).suffix
        slugname = Document.gen_slug() + suffiex
        filepath = path.join(upload_dir.document, slugname)
        
        with open(filepath, 'wb') as f:
            f.write(content)
        
        await self.crud.add(
            raw_filename=filename,
            slug=slugname,
            mime_type=mime_type,
            size=len(content)
        )
        document = await self.crud.get_by_slug(slugname)
        return document

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
        if document is not None:
            await self.crud.recoder_view(slugname)
            await self.crud.session.refresh(document)
            return document
        else:
            return None
        