from time import perf_counter
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlmodel.ext.asyncio.session import AsyncSession
from app.auth import get_current_user, get_optional_user, require_superuser
from app.database import get_session
from app.model import User
from app.service import ArticleService
from app.schema import (
    ArticleBatchCategoryIn,
    ArticleBatchCategoryOut,
    ArticleCreate,
    ArticleOut,
    ArticleSearchOut,
    ArticleSearchPageOut,
    ArticleStatsOut,
    ArticleUpdate,
    ArticleDetailOut,
    ArticleLikeOut,
    ArticleSort,
    PageResponse,
    SearchScope,
)
from app.types import (
    ARTICLE_DELETE_FORBIDDEN,
    ARTICLE_FORBIDDEN,
    ARTICLE_RESTORE_FORBIDDEN,
    CATEGORY_MANAGE_FORBIDDEN,
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
)


router = APIRouter()


def _ensure_can_modify(
    article_user_id: int, current_user: User, *, detail: str = ARTICLE_FORBIDDEN
) -> None:
    """非作者且非超管 → 403（不存在已在调用前用 404 拦截）"""
    if article_user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _resolve_visible_user_id(
    requested_user_id: Optional[int], current_user: Optional[User]
) -> Optional[int]:
    """列表可见范围：普通用户恒定只看自己的文章（user_id 参数被忽略）；
    超管按请求参数自由过滤；匿名（公开前台）不做限制"""
    if current_user is None or current_user.is_superuser:
        return requested_user_id
    return current_user.id


def _resolve_sort(
    requested_sort: Optional[ArticleSort], current_user: Optional[User]
) -> ArticleSort:
    """未显式传 sort 时按调用者取默认：匿名（前台新闻列表）按发布时间倒序；
    登录态（后台管理）按发布 id 倒序。显式传参优先。"""
    if requested_sort is not None:
        return requested_sort
    return ArticleSort.create_at if current_user is None else ArticleSort.id


def _normalize_keyword(keyword: Optional[str]) -> Optional[str]:
    """列表标题搜索：None 表示不过滤；纯空白 → 422（与 /articles/search 口径一致）"""
    if keyword is None:
        return None
    cleaned = keyword.strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="关键词不能为空",
        )
    return cleaned


@router.post("/", response_model=ArticleDetailOut, status_code=status.HTTP_201_CREATED)
async def create_article(
    data: ArticleCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # 业务校验失败（ServiceError）由全局 handler 统一转 400
    # data.user_id 显式指定发布主体；未传则归属当前登录用户；仅超管可指定他人
    author_id = data.user_id if data.user_id is not None else current_user.id
    if author_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权指定其他用户发布"
        )
    return await ArticleService(session).create(data, user_id=author_id)


@router.post("/batch-category", response_model=ArticleBatchCategoryOut)
async def batch_apply_category(
    data: ArticleBatchCategoryIn,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_superuser(CATEGORY_MANAGE_FORBIDDEN)),
):
    """批量将多篇文章加入/移出一个二级分类（仅超管；幂等；未知 slug 或无效分类返回 400）"""
    return await ArticleService(session).batch_category(data)


@router.get("/", response_model=PageResponse[ArticleOut])
async def list_articles(
    page: int = Query(default=DEFAULT_PAGE, ge=1, description="页码"),
    page_size: int = Query(
        default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="每页条数"
    ),
    category_id: Optional[int] = Query(default=None, ge=1, description="分类ID"),
    user_id: Optional[int] = Query(default=None, ge=1, description="作者用户ID"),
    is_deleted: bool = Query(
        default=False,
        description="false（默认）只返回未删除文章；true 只返回回收站文章（后台）",
    ),
    keyword: Optional[str] = Query(
        default=None,
        min_length=1,
        max_length=50,
        description="按标题模糊搜索（1~50 字；空格分隔多词 AND；后台管理用它定位文章后编辑）",
    ),
    sort: Optional[ArticleSort] = Query(
        default=None,
        description=(
            "排序字段（均倒序）：create_at=发布时间 / id=发布 id；"
            "不传时匿名默认 create_at、登录（后台管理）默认 id"
        ),
    ),
    session: AsyncSession = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """可见范围：匿名=公开全量；普通用户=固定只返回自己的文章（user_id 参数被忽略）；
    超管=全部（可按 user_id 过滤 / is_deleted 查回收站）。
    排序：不传 sort 时，匿名（前台）默认 create_at 发布时间倒序；登录（后台）默认 id 倒序。
    标题搜索：keyword 仅在上述可见范围内按标题过滤（后台管理定位文章后走 PATCH 编辑）。
    """
    resolved_sort = _resolve_sort(sort, current_user)
    service = ArticleService(session)
    return await service.list_paginated(
        page,
        page_size,
        category_id,
        _resolve_visible_user_id(user_id, current_user),
        is_deleted,
        order_by_field=resolved_sort.value,
        keyword=_normalize_keyword(keyword),
    )


@router.get("/search", response_model=ArticleSearchPageOut)
async def search_articles(
    keyword: str = Query(
        ...,
        min_length=1,
        max_length=50,
        description="搜索关键词；多个词用空格分隔（AND）",
    ),
    scope: SearchScope = Query(
        default=SearchScope.all,
        description="搜索范围：all=标题+正文（默认）/ title=仅标题 / content=仅正文",
    ),
    page: int = Query(default=DEFAULT_PAGE, ge=1, description="页码"),
    page_size: int = Query(
        default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="每页条数"
    ),
    category_id: Optional[int] = Query(
        default=None, ge=1, description="按二级分类 id 精确过滤"
    ),
    session: AsyncSession = Depends(get_session),
):
    """公开搜索：标题/正文关键词匹配（多词 AND），结果统一按发布时间倒序。

    摘要 `content_snippet` 为纯文本，高亮由前端根据 `matched_terms` 自行完成。
    """
    cleaned_keyword = keyword.strip()
    if not cleaned_keyword:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="关键词不能为空",
        )
    started_at = perf_counter()
    result = await ArticleService(session).search_paginated(
        keyword=cleaned_keyword,
        scope=scope,
        page=page,
        page_size=page_size,
        category_id=category_id,
    )
    # 服务端检索耗时（毫秒，保留 1 位小数）：前端据此展示「本次搜索耗时」
    elapsed_ms = round((perf_counter() - started_at) * 1000, 1)
    return ArticleSearchPageOut(**result.model_dump(), elapsed_ms=elapsed_ms)


@router.get("/stats", response_model=ArticleStatsOut)
async def article_stats(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """后台概览发布量统计（需登录）：

    - 超级管理员：本月新增文章数（全站，按 create_at 发布时间检索）
    - 普通用户：本人近 15 天发布的文章数
    """
    return await ArticleService(session).stats(current_user)


@router.get("/{slug}", response_model=ArticleDetailOut)
async def get_article(slug: str, session: AsyncSession = Depends(get_session)):
    """公开详情：每次访问 view_count +1（已删文章 404 且不计数）"""
    service = ArticleService(session)
    article = await service.view(slug)
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文章不存在")
    return article


@router.patch("/{slug}", response_model=ArticleDetailOut)
async def update_article(
    slug: str,
    data: ArticleUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """普通用户仅可改自己文章的正文类字段；超管可改任意文章并指定 user_id / create_at"""
    service = ArticleService(session)
    existing = await service.find_by_slug(slug)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文章不存在")
    _ensure_can_modify(existing.user_id, current_user)
    article = await service.update(
        slug, data, allow_admin_fields=current_user.is_superuser
    )
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文章不存在")
    return article


@router.post("/{slug}/like", response_model=ArticleLikeOut)
async def like_article(slug: str, session: AsyncSession = Depends(get_session)):
    """匿名点赞：公开接口，每次调用 +1"""
    service = ArticleService(session)
    like_count = await service.like(slug)
    if like_count is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文章不存在")
    return ArticleLikeOut(like_count=like_count)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_article(
    slug: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """软删除：作者本人或超管"""
    service = ArticleService(session)
    existing = await service.find_by_slug(slug)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文章不存在")
    _ensure_can_modify(existing.user_id, current_user, detail=ARTICLE_DELETE_FORBIDDEN)
    await service.delete(slug)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{slug}/restore", response_model=ArticleDetailOut)
async def restore_article(
    slug: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """恢复回收站中的文章（幂等）：作者本人或超管"""
    service = ArticleService(session)
    existing = await service.crud.get_by_slug(slug, include_deleted=True)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文章不存在")
    _ensure_can_modify(
        existing.user_id, current_user, detail=ARTICLE_RESTORE_FORBIDDEN
    )
    article = await service.restore(slug)
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文章不存在")
    return article
