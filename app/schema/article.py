from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schema.category import CategoryTree
from app.schema.user import UserOut


class ArticleSort(str, Enum):
    """GET /articles/ 排序字段（均为倒序）"""

    id = "id"  # 按发布 id 倒序（默认，最新创建在前）
    create_at = "create_at"  # 按发布时间倒序（最新发布在前，与 id 通常一致但可不同）


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
    user_id: int
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
    user_id: int
    categories: list[CategoryTree] = []
    user: UserOut | None = None


class ArticleCreate(BaseModel):
    title: str
    content: str | None = None
    cover_img_slug: str | None = None
    is_recommended: bool = False
    category_ids: list[int] = []
    # 指定发布主体（文章归属用户）；不传则取当前登录用户；仅超管可指定他人
    user_id: int | None = Field(default=None, ge=1)
    # 指定发布时间；不传用服务器当前时间；仅超管可指定
    create_at: datetime | None = None


class ArticleLikeOut(BaseModel):
    """匿名点赞响应：自增后的最新计数"""

    like_count: int


class ArticleUpdate(BaseModel):
    """部分更新。可空字段（content / cover_img_slug / category_ids）显式传 null 表示清空；
    非空字段（title / is_recommended / user_id / create_at）传 null 返回 400。
    user_id / create_at 仅超管生效，普通用户请求中出现会被忽略。
    view_count / like_count 不开放修改（走详情访问 / 点赞接口自增）。
    is_deleted 不走 PATCH：删除为 DELETE，恢复为 POST /articles/{slug}/restore。"""

    title: str | None = None
    content: str | None = None
    cover_img_slug: str | None = None
    is_recommended: bool | None = None
    category_ids: list[int] | None = None
    # 仅超管：改发布作者
    user_id: int | None = Field(default=None, ge=1)
    # 仅超管：改发布时间
    create_at: datetime | None = None


class ArticleBatchCategoryIn(BaseModel):
    """批量把多篇文章加入/移出某个二级分类（幂等；未知/已删 slug 整批 400）"""

    slugs: list[str] = Field(min_length=1)
    category_id: int
    mode: Literal["add", "remove"]


class ArticleBatchCategoryOut(BaseModel):
    """affected = 成功处理的未删除文章数"""

    affected: int
