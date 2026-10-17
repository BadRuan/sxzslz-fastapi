from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    raw_filename: str
    mime_type: str
    size_bytes: int
    view: int
    uploaded_at: datetime


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    raw_filename: str
    mime_type: str
    size_bytes: int
    view: int
    uploaded_at: datetime


class UploadResult(BaseModel):
    filename: str
    slug: str
    content_type: str
