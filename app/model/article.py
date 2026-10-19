from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4
from sqlmodel import Field, Relationship, SQLModel
from app.model.category import Category
if TYPE_CHECKING:
    from app.model.user import User


def generate_slug() -> str:
    return uuid4().hex[:16]


class ArticleCategory(SQLModel, table=True):
    __tablename__: str = "article_category"

    article_id: int = Field(primary_key=True)
    category_id: int = Field(primary_key=True)


class Article(SQLModel, table=True):
    __tablename__: str = "article"

    id: int = Field(primary_key=True, default=None)
    slug: str = Field(unique=True, default_factory=generate_slug)
    cover_img_slug: str | None = Field(default=None, nullable=True)
    title: str = Field(nullable=False)
    content: str | None = Field(default=None, nullable=True)
    user_id: int
    is_hidden: bool = Field(default=False)
    is_recommended: bool = Field(default=False)
    view_count: int = Field(default=0)
    like_count: int = Field(default=0)
    is_deleted: bool = Field(default=False)
    create_at: datetime = Field(default_factory=datetime.now)

    categories: list[Category] = Relationship(
        back_populates="articles",
        sa_relationship_kwargs={
            "secondary": "article_category",
            "primaryjoin": "Article.id == ArticleCategory.article_id",
            "secondaryjoin": "Category.id == ArticleCategory.category_id",
        },
    )
    user: "User" = Relationship(
        back_populates="articles",
        sa_relationship_kwargs={"primaryjoin": "User.id == foreign(Article.user_id)"},
    )
