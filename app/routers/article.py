from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlmodel.ext.asyncio.session import AsyncSession
from app.auth import get_current_user
from app.database import get_session
from app.model import User
from app.service import ArticleService
from app.schema import (
    ArticleCreate,
    ArticleUpdate,
    ArticleOut,
    ArticleDetailOut,
    ArticleLikeOut,
    PageResponse,
)


router = APIRouter()


@router.post("/", response_model=ArticleDetailOut, status_code=status.HTTP_201_CREATED)
async def create_article(
    data: ArticleCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    service = ArticleService(session)
    try:
        return await service.create(data, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


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
    _: User = Depends(get_current_user),
):
    service = ArticleService(session)
    try:
        article = await service.update(slug, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
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
    _: User = Depends(get_current_user),
):
    service = ArticleService(session)
    if not await service.delete(slug):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文章不存在")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{slug}/restore", response_model=ArticleDetailOut)
async def restore_article(
    slug: str,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """恢复回收站中的文章（幂等）：文章重新进入正常列表"""
    service = ArticleService(session)
    article = await service.restore(slug)
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文章不存在")
    return article
