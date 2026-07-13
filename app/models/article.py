from typing import Dict
from datetime import datetime
from uuid import uuid4
from sqlmodel import SQLModel, Field


def generate_slug() -> str:
    """生成唯一的 slug"""
    return uuid4().hex[:16]


class Article(SQLModel, table=True):
    __tablename__: str = "articles"

    # 编号
    id: int = Field(primary_key=True, default=None)  # type: ignore[arg-type]
    # 唯一url
    slug: str = Field(unique=True, default_factory=generate_slug)
    # 标题
    title: str = Field(nullable=False)
    # 内容
    content: str = Field(nullable=True)
    # 分类id
    category_id: int = Field(nullable=False)
    # 作者id
    user_id: int = Field(nullable=False)
    # 发布时间
    create_at: datetime = Field(default_factory=datetime.now)
    # 是否公开
    is_public: bool = Field(default=True)
    # 是否推荐
    is_recommended: bool = Field(default=False)
    # 阅读量
    view_count: int = Field(default=0)

    
    def __repr__(self) -> str:
        return f"<Article {self.title}>"

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "slug": self.slug,
            "title": self.title,
            "is_public": self.is_public,
            "is_recommended": self.is_recommended,
            "view_count": self.view_count,
            "create_at": self.create_at,
            "content": self.content
        }