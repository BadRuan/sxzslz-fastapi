from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict

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
    filename: str
    slug: str
    content_type: str
