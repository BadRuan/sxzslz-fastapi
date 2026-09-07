from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship


class ArticleCategory(SQLModel, table=True):
    __tablename__: str = "article_category"

    id: int = Field(primary_key=True, default=None)
    # 文章ID
    article_id: int = Field(foreign_key="article.id")
    # 分类ID
    category_id: int = Field(foreign_key="category.id")
    # 是否主分类：0否 1是
    is_primary: int = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.now)

    article: Optional["Article"] = Relationship(back_populates="category_links")
    category: Optional["Category"] = Relationship(back_populates="article_links")
