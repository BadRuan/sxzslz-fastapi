from enum import Enum
from os import path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth import get_current_user
from app.database import get_session
from app.model import Image, User
from app.routers._common import ensure_owner_or_superuser, to_upload_result_image, visible_user_id
from app.schema import ImageOut, ImageUpdate, PageResponse, UploadResult
from app.service import ImageService
from app.settings import upload_dir
from app.types import DEFAULT_PAGE, FILE_DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

router = APIRouter()


class ImageType(str, Enum):
    raw = "raw"
    preview = "preview"


@router.get("/", response_model=PageResponse[ImageOut])
async def get_images(
    page: int = Query(default=DEFAULT_PAGE, ge=1, description="页码"),
    page_size: int = Query(
        default=FILE_DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="每页条数"
    ),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """需登录：超管看全部，普通用户只看自己上传的"""
    return await ImageService(session).list_paginated(
        page, page_size, user_id=visible_user_id(current_user)
    )


@router.post("/", response_model=UploadResult)
async def upload_image(
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # 类型白名单 / 大小 / 空文件等校验在 service 层，ServiceError 由全局 handler 转 400
    image = await ImageService(session).add(
        filename=file.filename or "default_name",
        mime_type=file.content_type or "",
        file=file,
        user_id=current_user.id,
    )
    if image is None:
        raise HTTPException(status_code=400, detail="上传失败")
    return to_upload_result_image(image)


@router.post("/batch/", response_model=List[UploadResult])
async def upload_images_batch(
    files: List[UploadFile] = File(..., description="多张图片，表单字段名 files"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """多图同时上传（整批原子）：任一文件失败 → 400 整批不生效，不残留文件与记录"""
    images = await ImageService(session).add_many(files, user_id=current_user.id)
    return [to_upload_result_image(image) for image in images]


@router.get("/{slug}")
async def get_image(
    slug: str,
    file_type: ImageType = Query(default=ImageType.preview, description="返回原图或预览图"),
    raw: bool = Query(default=False, description="true 等价于 file_type=raw，便于前端直接拼 ?raw=1"),
    session: AsyncSession = Depends(get_session),
):
    """公开读取图片本体（文章封面等前台场景依赖此接口，不限制上传者）

    默认返回 WebP 预览图（省流量）；`?raw=1` 或 `?file_type=raw` 返回原图，
    前台「点击查看原图」应当使用原图地址。
    """
    service = ImageService(session)
    image = await service.get_by_slug(slug)
    if image is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Image not found"
        )

    wants_raw = raw or file_type == ImageType.raw
    if wants_raw:
        file_path = path.join(upload_dir.image_raw, slug)
        media_type = image.mime_type
    else:
        slug_base, _ = path.splitext(slug)
        file_path = path.join(upload_dir.image_preview, slug_base + ".webp")
        # 预览图固定为 WebP，不能沿用原图的 MIME
        media_type = "image/webp"

    return FileResponse(
        path=file_path,
        media_type=media_type,
        headers={
            "Content-Disposition": "inline",
            # slug 即内容标识，可长缓存；并禁止浏览器按内容猜 MIME
            "Cache-Control": "public, max-age=604800",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.patch("/{slug}", response_model=ImageOut)
async def update_image(
    slug: str,
    data: ImageUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """仅上传者本人或超管可改展示名"""
    service = ImageService(session)
    image = await service.find_by_slug(slug)
    if image is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Image not found"
        )
    ensure_owner_or_superuser(image.user_id, current_user)
    updated = await service.rename(slug, data.raw_filename)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Image not found"
        )
    return updated


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_image(
    slug: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """仅上传者本人或超管可删：DB 记录 + 磁盘文件（原图/预览图）一并清理"""
    service = ImageService(session)
    image = await service.find_by_slug(slug)
    if image is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Image not found"
        )
    ensure_owner_or_superuser(image.user_id, current_user)
    await service.remove_by_slug(slug)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
