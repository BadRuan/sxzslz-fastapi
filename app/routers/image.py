from enum import Enum
from os import path

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth import get_current_user
from app.database import get_session
from app.model import User
from app.schema import ImageOut, ImageUpdate, PageResponse, UploadResult
from app.service import ImageService
from app.settings import allow_type, upload_dir, IMAGE_TYPE_LABEL

router = APIRouter()


class ImageType(str, Enum):
    raw = "raw"
    preview = "preview"


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


@router.get("/", response_model=PageResponse[ImageOut])
async def get_images(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=30, ge=1, le=100, description="每页条数"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """需登录：超管看全部，普通用户只看自己上传的"""
    return await ImageService(session).list_paginated(
        page, page_size, user_id=_visible_user_id(current_user)
    )


@router.post("/", response_model=UploadResult)
async def upload_image(
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in allow_type.image:
        received = file.content_type or "未知"
        raise HTTPException(
            status_code=400,
            detail=f"不支持的图片类型「{received}」，仅支持 {IMAGE_TYPE_LABEL} 格式",
        )

    filename = file.filename or "default_name"
    service = ImageService(session)
    # ServiceError（超限/空文件/落盘失败）由全局 handler 转 400
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
    """公开读取图片本体（文章封面等前台场景依赖此接口，不限制上传者）"""
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
    _ensure_owner_or_superuser(image.user_id, current_user)
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
    _ensure_owner_or_superuser(image.user_id, current_user)
    await service.remove_by_slug(slug)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
