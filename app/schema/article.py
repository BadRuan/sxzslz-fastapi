from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schema.category import CategoryTree
from app.schema.user import UserOut


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    cover_img_slug: str | None = None
    title: str
    is_deleted: bool
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
    is_deleted: bool
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
    is_recommended: bool = False
    category_ids: list[int] = []


class ArticleLikeOut(BaseModel):
    """匿名点赞响应：自增后的最新计数"""

    like_count: int


class ArticleUpdate(BaseModel):
    """部分更新。可空字段（content / cover_img_slug / category_ids）显式传 null 表示清空；
    非空字段（title / is_recommended）传 null 返回 400。
    is_deleted 不走 PATCH：删除为 DELETE，恢复为 POST /articles/{slug}/restore。"""

    title: str | None = None
    content: str | None = None
    cover_img_slug: str | None = None
    is_recommended: bool | None = None
    category_ids: list[int] | None = None


class ArticleBatchCategoryIn(BaseModel):
    """批量把多篇文章加入/移出某个二级分类（幂等；未知/已删 slug 整批 400）"""

    slugs: list[str] = Field(min_length=1)
    category_id: int
    mode: Literal["add", "remove"]


class ArticleBatchCategoryOut(BaseModel):
    """affected = 成功处理的未删除文章数"""

    affected: int
