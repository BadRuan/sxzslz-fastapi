from typing import TYPE_CHECKING

from sqlalchemy import Index
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.model.article import Article


class Category(SQLModel, table=True):

    __tablename__: str = "category"

    id: int = Field(primary_key=True, default=None)
    name: str = Field(nullable=False)
    parent_id: int = Field(default=0)
    sort: int = Field(default=0, nullable=False)

    __table_args__ = (Index("uq_category_name", "name"),)

    articles: list["Article"] = Relationship(
        back_populates="categories",
        sa_relationship_kwargs={
            "secondary": "article_category",
            "primaryjoin": "Category.id == ArticleCategory.category_id",
            "secondaryjoin": "Article.id == ArticleCategory.article_id",
        },
    )
