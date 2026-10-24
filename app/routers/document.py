from os import path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth import get_current_user
from app.database import get_session
from app.model import User
from app.schema import DocumentOut, PageResponse, UploadResult
from app.service import DocumentService
from app.settings import allow_type, upload_dir

router = APIRouter()


@router.get("/", response_model=PageResponse[DocumentOut])
async def get_documents(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=30, ge=1, le=100, description="每页条数"),
    session: AsyncSession = Depends(get_session),
):
    service = DocumentService(session)
    return await service.list_paginated(page, page_size)


@router.post("/", response_model=UploadResult)
async def upload_document(
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    if file.content_type not in allow_type.document:
        raise HTTPException(
            status_code=400,
            detail="仅支持txt、pdf、doc、docx、xls、xlsx、ppt、pptx、zip格式的文件",
        )

    filename = file.filename or "default_name"
    content = await file.read()
    service = DocumentService(session)
    doc = await service.add(
        filename=filename, mime_type=str(file.content_type), content=content
    )
    if doc is None:
        raise HTTPException(status_code=400, detail="上传失败")
    return UploadResult(
        filename=file.filename or filename,
        slug=doc.slug,
        content_type=str(file.content_type),
    )


@router.get("/{slug}")
async def get_document(slug: str, session: AsyncSession = Depends(get_session)):
    service = DocumentService(session)
    doc = await service.get_by_slug(slug)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    return FileResponse(
        filename=doc.raw_filename,
        path=path.join(upload_dir.document, slug),
        media_type=doc.mime_type,
    )
