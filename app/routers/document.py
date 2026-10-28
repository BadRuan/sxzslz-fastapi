from os import path

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth import get_current_user
from app.database import get_session
from app.model import User
from app.schema import (
    DocumentOut,
    DocumentSort,
    DocumentUpdate,
    PageResponse,
    UploadResult,
)
from app.service import DocumentService
from app.settings import allow_type, upload_dir

router = APIRouter()


def _ensure_owner(document_user_id: int, current_user: User) -> None:
    """非本人操作 → 403（不存在已在调用前用 404 拦截）"""
    if document_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作该文件"
        )


@router.get("/", response_model=PageResponse[DocumentOut])
async def get_documents(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=30, ge=1, le=100, description="每页条数"),
    sort: DocumentSort = Query(
        default=DocumentSort.uploaded_at,
        description="排序字段（倒序）：uploaded_at=上传时间（默认）/ view=浏览量",
    ),
    session: AsyncSession = Depends(get_session),
):
    return await DocumentService(session).list_paginated(page, page_size, sort)


@router.post("/", response_model=UploadResult)
async def upload_document(
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in allow_type.document:
        received = file.content_type or "未知"
        raise HTTPException(
            status_code=400,
            detail=(
                f"不支持的文件类型「{received}」，"
                "仅支持 txt、pdf、doc、docx、xls、xlsx、ppt、pptx、zip 格式"
            ),
        )

    filename = file.filename or "default_name"
    service = DocumentService(session)
    # ServiceError（超限/空文件）由全局 handler 转 400
    doc = await service.add(
        filename=filename,
        mime_type=str(file.content_type),
        file=file,
        user_id=current_user.id,
    )
    if doc is None:
        raise HTTPException(status_code=400, detail="上传失败")
    slug = doc.slug
    return UploadResult(
        filename=doc.raw_filename,
        slug=slug,
        content_type=doc.mime_type,
        size_bytes=doc.size_bytes,
        url=f"/document/{slug}",
    )


@router.patch("/{slug}", response_model=DocumentOut)
async def update_document(
    slug: str,
    data: DocumentUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """仅上传者可改展示名（下载时 Content-Disposition 用）；不替换文件内容"""
    service = DocumentService(session)
    doc = await service.find_by_slug(slug)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    _ensure_owner(doc.user_id, current_user)
    updated = await service.rename(slug, data.raw_filename)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    return updated


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    slug: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """仅上传者可删：DB 记录 + 磁盘文件一并清理"""
    service = DocumentService(session)
    doc = await service.find_by_slug(slug)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    _ensure_owner(doc.user_id, current_user)
    await service.remove(slug)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
