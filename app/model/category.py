from typing import List
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship


class Category(SQLModel, table=True):
    __tablename__: str = "category"

    id: int = Field(primary_key=True, default=None)
    name: str = Field(unique=True, nullable=False)
    slug: str = Field(unique=True, nullable=False)
    parent_id: int = Field(default=0, foreign_key="category.id")
    # 层级路径，如 /1/3/7/
    path: str = Field(nullable=False)
    # 层级深度，顶级为1
    level: int = Field(nullable=False)
    # 排序值，越小越靠前
    sort: int = Field(default=0, nullable=False)
    created_at: datetime = Field(default_factory=datetime.now)

    article_links: List["ArticleCategory"] = Relationship(back_populates="category")