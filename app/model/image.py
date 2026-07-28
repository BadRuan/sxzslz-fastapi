from uuid import uuid4
from datetime import datetime
from sqlmodel import SQLModel, Field


class Image(SQLModel, table=True):
    __tablename__: str = "image_records"

    id: int = Field(primary_key=True, default=None)
    slug: str = Field(max_length=50, unique=True)
    raw_filename: str = Field(max_length=255)
    mime_type: str = Field(max_length=50)
    size_bytes: int
    view: int = Field(default=0)
    uploaded_at: datetime = Field(default_factory=datetime.now)
    
    @staticmethod
    def gen_slug():
        return uuid4().hex
    