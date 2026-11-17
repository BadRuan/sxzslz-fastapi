"""文件（图片 / 文档）路由的共用辅助函数。

两套路由原本各自维护一份 `_ensure_owner_or_superuser` / `_visible_user_id` /
`_to_upload_result`，现集中于此，避免同一份逻辑在多处重复维护。
"""

from typing import Optional

from fastapi import HTTPException, status

from app.model import Document, Image, User
from app.schema import UploadResult
from app.types import FILE_FORBIDDEN


def ensure_owner_or_superuser(
    owner_id: int, current_user: User, *, forbidden_detail: str = FILE_FORBIDDEN
) -> None:
    """非本人且非超管 → 403（不存在已在调用前用 404 拦截）"""
    if owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=forbidden_detail
        )


def visible_user_id(current_user: User) -> Optional[int]:
    """列表可见范围：超管 None=全部；普通用户=仅自己"""
    return None if current_user.is_superuser else current_user.id


def to_upload_result_image(image: Image) -> UploadResult:
    """Image 记录 → 上传响应（单文件与批量共用）"""
    slug = image.slug
    return UploadResult(
        filename=image.raw_filename,
        slug=slug,
        content_type=image.mime_type,
        size_bytes=image.size_bytes,
        url=f"/image/{slug}",
        raw_url=f"/image/{slug}?file_type=raw",
    )


def to_upload_result_document(document: Document) -> UploadResult:
    """Document 记录 → 上传响应（单文件与批量共用；无 raw_url）"""
    slug = document.slug
    return UploadResult(
        filename=document.raw_filename,
        slug=slug,
        content_type=document.mime_type,
        size_bytes=document.size_bytes,
        url=f"/document/{slug}",
    )


__all__ = [
    "ensure_owner_or_superuser",
    "visible_user_id",
    "to_upload_result_image",
    "to_upload_result_document",
]
