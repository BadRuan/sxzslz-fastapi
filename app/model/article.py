from typing import List, Optional
from datetime import datetime
from uuid import uuid4
from sqlmodel import SQLModel, Field, Relationship


def generate_slug() -> str:
    """生成唯一的 slug"""
    return uuid4().hex[:16]


class Article(SQLModel, table=True):
    __tablename__: str = "article"

    id: int = Field(primary_key=True, default=None)
    slug: str = Field(unique=True, default_factory=generate_slug)
    cover_img_slug: Optional[str] = Field(default=None, nullable=True)
    title: str = Field(nullable=False)
    content: Optional[str] = Field(default=None, nullable=True)
    user_id: int = Field(foreign_key="user.id")
    # 状态：0草稿 1已发布 2下线
    status: int = Field(default=1)
    is_recommended: bool = Field(default=False)
    view_count: int = Field(default=0)
    like_count: int = Field(default=0)
    create_at: datetime = Field(default_factory=datetime.now)

    category_links: List["ArticleCategory"] = Relationship(back_populates="article")
