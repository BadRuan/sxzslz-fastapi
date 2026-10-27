from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schema.user import UserOut


class DocumentSort(str, Enum):
    """GET /document/ 排序字段（均为倒序）"""

    uploaded_at = "uploaded_at"  # 默认：最新上传在前
    view = "view"  # 浏览量最热在前


class ImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    raw_filename: str
    mime_type: str
    size_bytes: int
    user_id: int
    view: int
    uploaded_at: datetime
    user: UserOut | None = None  # 上传者（业务层关联）；用户不存在时为 None


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    raw_filename: str
    mime_type: str
    size_bytes: int
    user_id: int
    view: int
    uploaded_at: datetime
    user: UserOut | None = None  # 上传者（业务层关联）；用户不存在时为 None


class UploadResult(BaseModel):
    """上传成功反馈：前端可直接用 url 拼展示/下载地址"""

    filename: str
    slug: str
    content_type: str
    size_bytes: int
    # 相对路径，前端拼 BASE 后使用；图片为预览图地址，文件为下载地址
    url: str
    # 仅图片有值：原图地址（?file_type=raw）；文档为 None
    raw_url: str | None = None


class DocumentUpdate(BaseModel):
    """PATCH /document/{slug}：仅支持改展示名（下载时的文件名），不替换文件内容"""

    raw_filename: str = Field(min_length=1, max_length=255)
