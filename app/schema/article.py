from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schema.category import CategoryTree
from app.schema.user import UserOut


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    cover_img_slug: str | None = None
    title: str
    is_hidden: bool
    is_recommended: bool
    create_at: datetime
    view_count: int
    like_count: int
    categories: list[CategoryTree] = []
    user: UserOut | None = None


class ArticleDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    cover_img_slug: str | None = None
    title: str
    content: str | None = None
    is_hidden: bool
    is_recommended: bool
    create_at: datetime
    view_count: int
    like_count: int
    categories: list[CategoryTree] = []
    user: UserOut | None = None


class ArticleCreate(BaseModel):
    title: str
    content: str | None = None
    cover_img_slug: str | None = None
    is_hidden: bool = False
    is_recommended: bool = False
    category_ids: list[int] = []


class ArticleUpdate(BaseModel):
    """部分更新。可空字段（content / cover_img_slug / category_ids）显式传 null 表示清空；
    非空字段（title / is_hidden / is_recommended）传 null 返回 400。"""

    title: str | None = None
    content: str | None = None
    cover_img_slug: str | None = None
    is_hidden: bool | None = None
    is_recommended: bool | None = None
    category_ids: list[int] | None = None
