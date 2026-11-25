from enum import Enum
from os import path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth import get_current_user
from app.database import get_session
from app.model import Document, User
from app.routers._common import client_info, ensure_owner_or_superuser, to_upload_result_document, visible_user_id
from app.schema import DocumentOut, DocumentSort, DocumentUpdate, PageResponse, UploadResult
from app.service import DocumentService
from app.settings import upload_dir
from app.types import DEFAULT_PAGE, FILE_DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

router = APIRouter()


# 上传文件的 slug 即内容标识，同一 slug 不会变内容，可放心让浏览器长缓存
_FILE_CACHE_HEADERS = {
    "Cache-Control": "public, max-age=604800",
    "X-Content-Type-Options": "nosniff",
}


def _file_headers() -> dict[str, str]:
    return dict(_FILE_CACHE_HEADERS)


@router.get("/", response_model=PageResponse[DocumentOut])
async def get_documents(
    page: int = Query(default=DEFAULT_PAGE, ge=1, description="页码"),
    page_size: int = Query(
        default=FILE_DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="每页条数"
    ),
    sort: DocumentSort = Query(
        default=DocumentSort.uploaded_at,
        description="排序字段（倒序）：uploaded_at=上传时间（默认）/ view=浏览量",
    ),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """需登录：超管看全部，普通用户只看自己上传的"""
    return await DocumentService(session).list_paginated(
        page, page_size, sort, user_id=visible_user_id(current_user)
    )


@router.post("/", response_model=UploadResult)
async def upload_document(
    request: Request,
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    client_ip, user_agent = client_info(request)
    # 类型白名单 / 大小 / 空文件等校验在 service 层，ServiceError 由全局 handler 转 400
    document = await DocumentService(session).add(
        filename=file.filename or "default_name",
        mime_type=file.content_type or "",
        file=file,
        user_id=current_user.id,
        operator_id=current_user.id,
        operator_name=current_user.nickname,
        client_ip=client_ip,
        user_agent=user_agent,
    )
    if document is None:
        raise HTTPException(status_code=400, detail="上传失败")
    return to_upload_result_document(document)


@router.post("/batch/", response_model=List[UploadResult])
async def upload_documents_batch(
    files: List[UploadFile] = File(..., description="多个文件，表单字段名 files"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """多文件同时上传（整批原子）：任一文件失败 → 400 整批不生效，不残留文件与记录"""
    documents = await DocumentService(session).add_many(files, user_id=current_user.id)
    return [to_upload_result_document(document) for document in documents]


@router.patch("/{slug}", response_model=DocumentOut)
async def update_document(
    request: Request,
    slug: str,
    data: DocumentUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """仅上传者本人或超管可改展示名（下载时 Content-Disposition 用）；不替换文件内容"""
    client_ip, user_agent = client_info(request)
    service = DocumentService(session)
    doc = await service.find_by_slug(slug)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    ensure_owner_or_superuser(doc.user_id, current_user)
    updated = await service.rename(
        slug,
        data.raw_filename,
        operator_id=current_user.id,
        operator_name=current_user.nickname,
        client_ip=client_ip,
        user_agent=user_agent,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    return updated


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    request: Request,
    slug: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """仅上传者本人或超管可删：DB 记录 + 磁盘文件一并清理"""
    client_ip, user_agent = client_info(request)
    service = DocumentService(session)
    doc = await service.find_by_slug(slug)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    ensure_owner_or_superuser(doc.user_id, current_user)
    await service.remove(
        slug,
        operator_id=current_user.id,
        operator_name=current_user.nickname,
        client_ip=client_ip,
        user_agent=user_agent,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{slug}")
async def get_document(
    slug: str,
    inline: bool = Query(
        default=False,
        description="true=浏览器内联打开（在线预览）；false=作为附件下载（默认）",
    ),
    session: AsyncSession = Depends(get_session),
):
    """读取文件：公开访问（无需鉴权）

    `inline=true` 返回 `Content-Disposition: inline`，浏览器/iframe 可直接渲染
    （PDF、图片、纯文本等）；默认仍是附件下载，保持原有调用方行为不变。
    """
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
        content_disposition_type="inline" if inline else "attachment",
        headers=_file_headers(),
    )
