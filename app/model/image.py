from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4
from sqlalchemy.orm import foreign
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.model.user import User


def generate_slug() -> str:
    return uuid4().hex


class Image(SQLModel, table=True):
    __tablename__: str = "image"

    id: int = Field(primary_key=True, default=None)
    slug: str = Field(max_length=50, unique=True)
    raw_filename: str = Field(max_length=255)
    mime_type: str = Field(max_length=50)
    size_bytes: int
    # 业务层关联上传者，无数据库外键；必填，由上传接口写入当前登录用户
    user_id: int
    view: int = Field(default=0)
    uploaded_at: datetime = Field(default_factory=datetime.now)

    user: "User" = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": "User.id == foreign(Image.user_id)",
        }
    )
