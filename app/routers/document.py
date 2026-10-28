from enum import Enum
from os import path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth import get_current_user
from app.database import get_session
from app.model import Document, User
from app.schema import DocumentOut, DocumentSort, DocumentUpdate, PageResponse, UploadResult
from app.service import DocumentService
from app.settings import upload_dir

router = APIRouter()


def _ensure_owner_or_superuser(
    owner_id: int, current_user: User, *, forbidden_detail: str = "无权限操作该文件"
) -> None:
    """非本人且非超管 → 403（不存在已在调用前用 404 拦截）"""
    if owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=forbidden_detail
        )


def _visible_user_id(current_user: User) -> int | None:
    """列表可见范围：超管 None=全部；普通用户=仅自己"""
    return None if current_user.is_superuser else current_user.id


def _to_upload_result(document: Document) -> UploadResult:
    """Document 记录 → 上传响应（单文件与批量共用）"""
    slug = document.slug
    return UploadResult(
        filename=document.raw_filename,
        slug=slug,
        content_type=document.mime_type,
        size_bytes=document.size_bytes,
        url=f"/document/{slug}",
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
    current_user: User = Depends(get_current_user),
):
    """需登录：超管看全部，普通用户只看自己上传的"""
    return await DocumentService(session).list_paginated(
        page, page_size, sort, user_id=_visible_user_id(current_user)
    )


@router.post("/", response_model=UploadResult)
async def upload_document(
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # 类型白名单 / 大小 / 空文件等校验在 service 层，ServiceError 由全局 handler 转 400
    document = await DocumentService(session).add(
        filename=file.filename or "default_name",
        mime_type=file.content_type or "",
        file=file,
        user_id=current_user.id,
    )
    if document is None:
        raise HTTPException(status_code=400, detail="上传失败")
    return _to_upload_result(document)


@router.post("/batch/", response_model=List[UploadResult])
async def upload_documents_batch(
    files: List[UploadFile] = File(..., description="多个文件，表单字段名 files"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """多文件同时上传（整批原子）：任一文件失败 → 400 整批不生效，不残留文件与记录"""
    documents = await DocumentService(session).add_many(
        files, user_id=current_user.id
    )
    return [_to_upload_result(document) for document in documents]


@router.patch("/{slug}", response_model=DocumentOut)
async def update_document(
    slug: str,
    data: DocumentUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """仅上传者本人或超管可改展示名（下载时 Content-Disposition 用）；不替换文件内容"""
    service = DocumentService(session)
    doc = await service.find_by_slug(slug)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    _ensure_owner_or_superuser(doc.user_id, current_user)
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
    """仅上传者本人或超管可删：DB 记录 + 磁盘文件一并清理"""
    service = DocumentService(session)
    doc = await service.find_by_slug(slug)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    _ensure_owner_or_superuser(doc.user_id, current_user)
    await service.remove(slug)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{slug}")
async def get_document(
    slug: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """下载文件：仅上传者本人或超管（普通用户不能下他人文件）"""
    service = DocumentService(session)
    doc = await service.get_by_slug(slug)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    _ensure_owner_or_superuser(
        doc.user_id, current_user, forbidden_detail="无权限查看该文件"
    )
    return FileResponse(
        filename=doc.raw_filename,
        path=path.join(upload_dir.document, slug),
        media_type=doc.mime_type,
    )
