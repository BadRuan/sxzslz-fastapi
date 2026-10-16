from typing import TYPE_CHECKING, List, Optional
from datetime import datetime
from uuid import uuid4
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy.orm import foreign
if TYPE_CHECKING:
    from app.model.user import User

def generate_slug() -> str:
    return uuid4().hex[:16]

class ArticleCategory(SQLModel, table=True):
    __tablename__: str = "article_category"

    article_id: int = Field(primary_key=True)
    category_id: int = Field(primary_key=True)

class Category(SQLModel, table=True):
    __tablename__: str = "category"

    id: int = Field(primary_key=True, default=None)
    name: str = Field(unique=True, nullable=False)
    slug: str = Field(unique=True, nullable=False)
    parent_id: int = Field(default=0)
    # 层级路径，如 /1/3/7/
    path: str = Field(nullable=False)
    # 层级深度，顶级为1
    level: int = Field(nullable=False)
    # 排序值，越小越靠前
    sort: int = Field(default=0, nullable=False)
    is_deleted: bool = Field(default=False)
    
    articles: List['Article'] = Relationship(
        back_populates="categories",
        sa_relationship_kwargs= {
            "secondary": "article_category",
            "primaryjoin": "Category.id == ArticleCategory.category_id",
            "secondaryjoin": "Article.id == ArticleCategory.article_id",
        }
    )

class Article(SQLModel, table=True):
    __tablename__: str = "article"

    id: int = Field(primary_key=True, default=None)
    slug: str = Field(unique=True, default_factory=generate_slug)
    cover_img_slug: Optional[str] = Field(default=None, nullable=True)
    title: str = Field(nullable=False)
    content: Optional[str] = Field(default=None, nullable=True)
    user_id: int
    is_hidden: bool = Field(default=False)
    is_recommended: bool = Field(default=False)
    view_count: int = Field(default=0)
    like_count: int = Field(default=0)
    is_deleted: bool = Field(default=False)
    create_at: datetime = Field(default_factory=datetime.now)

    categories: List['Category'] = Relationship(
        back_populates="articles",
        sa_relationship_kwargs={
            "secondary": "article_category",
            "primaryjoin": "Article.id == ArticleCategory.article_id",
            "secondaryjoin": "Category.id == ArticleCategory.category_id",
        }
    )
    user: 'User' = Relationship(
        back_populates="articles",
        sa_relationship_kwargs={
            "primaryjoin": "User.id == foreign(Article.user_id)"
        }
    )
