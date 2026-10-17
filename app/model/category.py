from typing import TYPE_CHECKING

from sqlalchemy import Index, text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.model.article import Article


class Category(SQLModel, table=True):
    __tablename__: str = "category"

    id: int = Field(primary_key=True, default=None)
    # name/slug 唯一性由下方部分索引约束（仅活跃行），软删后可复用
    name: str = Field(nullable=False)
    slug: str = Field(nullable=False)
    parent_id: int = Field(default=0)
    # 层级路径，如 /1/3/7/
    path: str = Field(nullable=False)
    # 层级深度，顶级为1
    level: int = Field(nullable=False)
    # 排序值，越小越靠前
    sort: int = Field(default=0, nullable=False)
    is_deleted: bool = Field(default=False)

    __table_args__ = (
        Index(
            "uq_category_name",
            "name",
            unique=True,
            postgresql_where=text("NOT is_deleted"),
            sqlite_where=text("NOT is_deleted"),
        ),
        Index(
            "uq_category_slug",
            "slug",
            unique=True,
            postgresql_where=text("NOT is_deleted"),
            sqlite_where=text("NOT is_deleted"),
        ),
    )

    articles: list["Article"] = Relationship(
        back_populates="categories",
        sa_relationship_kwargs={
            "secondary": "article_category",
            "primaryjoin": "Category.id == ArticleCategory.category_id",
            "secondaryjoin": "Article.id == ArticleCategory.article_id",
        },
    )
