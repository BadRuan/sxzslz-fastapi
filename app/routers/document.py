from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession
from os import path
from fastapi import Depends, UploadFile, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlmodel.ext.asyncio.session import AsyncSession
from app.settings import upload_dir, allow_type
from app.database import get_session
from app.service import DocumentService
from app.model import PageResponse


router = APIRouter()

   
@router.get('/', response_model=PageResponse)
async def get_documents(
    page: int = Query(default=1, ge=1 ,description='页码'),
    page_size: int = Query(default=30, ge=1, le=100, description='每页条数'),
    session: AsyncSession = Depends(get_session)
):
    service = DocumentService(session)
    return await service.list_paginated(page, page_size)

@router.post('/')
async def create_upload_file(file: UploadFile, session: AsyncSession = Depends(get_session)):
    if file.content_type not in allow_type.document:
        raise HTTPException(
            status_code=400,
            detail="仅支持txt、pdf、doc、docx、xls、xlsx格式的文件"
        )
    
    filename = file.filename or 'default_name'
    content = await file.read()
    service = DocumentService(session)
    _file = await service.add(filename=filename, mime_type=str(file.content_type), content=content)
    if _file is not None:
        return {
        "filename": file.filename, 
        "slug": _file.slug,
        "content_type": file.content_type,
        }
    else:
        raise HTTPException(
            status_code=400,
            detail="上传失败"
        )

@router.get('/{slug}')
async def get_document(slug, session: AsyncSession = Depends(get_session)):
    service = DocumentService(session)
    _file = await service.get_by_slug(slug)
    if _file is not None:
        return FileResponse(
                filename=_file.raw_filename,
                path=path.join(upload_dir.document, slug), 
                media_type=_file.mime_type,  
        )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, 
        detail='Document not found'
    )
