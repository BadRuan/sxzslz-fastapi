from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlmodel.ext.asyncio.session import AsyncSession
from app.database import get_session
from app.service import ArticleService
from app.schema import ArticleCreate, ArticleUpdate, ArticleOut, ArticleDetailOut, PageResponse


router = APIRouter()


@router.post("/", response_model=ArticleDetailOut, status_code=status.HTTP_201_CREATED)
async def create_article(data: ArticleCreate, session: AsyncSession = Depends(get_session)):
    service = ArticleService(session)
    try:
        return await service.create(data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/", response_model=PageResponse[ArticleOut])
async def list_articles(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    category_id: Optional[int] = Query(default=None, ge=1, description="分类ID"),
    session: AsyncSession = Depends(get_session),
):
    service = ArticleService(session)
    return await service.list_paginated(page, page_size, category_id)


@router.get("/{slug}", response_model=ArticleDetailOut)
async def get_article(slug: str, session: AsyncSession = Depends(get_session)):
    service = ArticleService(session)
    article = await service.get_by_slug(slug)
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文章不存在")
    return article


@router.patch("/{slug}", response_model=ArticleDetailOut)
async def update_article(
    slug: str, data: ArticleUpdate, session: AsyncSession = Depends(get_session)
):
    service = ArticleService(session)
    try:
        article = await service.update(slug, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文章不存在")
    return article


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_article(slug: str, session: AsyncSession = Depends(get_session)):
    service = ArticleService(session)
    if not await service.delete(slug):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文章不存在")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
