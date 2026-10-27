from enum import Enum
from os import path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth import get_current_user
from app.database import get_session
from app.model import User
from app.schema import ImageOut, PageResponse, UploadResult
from app.service import ImageService
from app.settings import allow_type, upload_dir

router = APIRouter()


class ImageType(str, Enum):
    raw = "raw"
    preview = "preview"


@router.get("/", response_model=PageResponse[ImageOut])
async def get_images(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=30, ge=1, le=100, description="每页条数"),
    session: AsyncSession = Depends(get_session),
):
    service = ImageService(session)
    return await service.list_paginated(page, page_size)


@router.post("/", response_model=UploadResult)
async def upload_image(
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in allow_type.image:
        raise HTTPException(
            status_code=400, detail="仅支持 JPG, PNG, GIF, WebP 格式的图片"
        )

    filename = file.filename or "default_name"
    service = ImageService(session)
    # ServiceError（超限/空文件）由全局 handler 转 400
    image = await service.add(
        filename=filename,
        mime_type=str(file.content_type),
        file=file,
        user_id=current_user.id,
    )
    if image is None:
        raise HTTPException(status_code=400, detail="上传失败")
    slug = image.slug
    return UploadResult(
        filename=image.raw_filename,
        slug=slug,
        content_type=image.mime_type,
        size_bytes=image.size_bytes,
        url=f"/image/{slug}",
        raw_url=f"/image/{slug}?file_type=raw",
    )


@router.get("/{slug}")
async def get_image(
    slug: str,
    file_type: ImageType = Query(default=ImageType.preview, description="返回原图或预览图"),
    session: AsyncSession = Depends(get_session),
):
    service = ImageService(session)
    image = await service.get_by_slug(slug)
    if image is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Image not found"
        )

    if file_type == ImageType.raw:
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
        headers={"Content-Disposition": "inline"},
    )
