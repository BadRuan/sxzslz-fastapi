from datetime import datetime
from uuid import uuid4
from sqlmodel import Field, SQLModel


def generate_slug() -> str:
    return uuid4().hex


class Image(SQLModel, table=True):
    __tablename__: str = "image"

    id: int = Field(primary_key=True, default=None)
    slug: str = Field(max_length=50, unique=True)
    raw_filename: str = Field(max_length=255)
    mime_type: str = Field(max_length=50)
    size_bytes: int
    view: int = Field(default=0)
    uploaded_at: datetime = Field(default_factory=datetime.now)
