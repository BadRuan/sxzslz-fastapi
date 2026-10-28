from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlmodel.ext.asyncio.session import AsyncSession
from app.auth import get_current_user
from app.database import get_session
from app.model import User
from app.service import ArticleService
from app.schema import (
    ArticleBatchCategoryIn,
    ArticleBatchCategoryOut,
    ArticleCreate,
    ArticleUpdate,
    ArticleOut,
    ArticleDetailOut,
    ArticleLikeOut,
    PageResponse,
)


router = APIRouter()


def _ensure_can_modify(
    article_user_id: int, current_user: User, *, detail: str = "无权修改他人文章"
) -> None:
    """非作者且非超管 → 403（不存在已在调用前用 404 拦截）"""
    if article_user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


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
    _: User = Depends(get_current_user),
):
    """批量将多篇文章加入/移出一个二级分类（幂等；未知 slug 或无效分类返回 400）"""
    return await ArticleService(session).batch_category(data)


@router.get("/", response_model=PageResponse[ArticleOut])
async def list_articles(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    category_id: Optional[int] = Query(default=None, ge=1, description="分类ID"),
    user_id: Optional[int] = Query(default=None, ge=1, description="作者用户ID"),
    is_deleted: bool = Query(
        default=False,
        description="false（默认）只返回未删除文章；true 只返回回收站文章（后台）",
    ),
    session: AsyncSession = Depends(get_session),
):
    service = ArticleService(session)
    return await service.list_paginated(page, page_size, category_id, user_id, is_deleted)


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
    _ensure_can_modify(existing.user_id, current_user, detail="无权删除他人文章")
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
    _ensure_can_modify(existing.user_id, current_user, detail="无权恢复他人文章")
    article = await service.restore(slug)
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文章不存在")
    return article
