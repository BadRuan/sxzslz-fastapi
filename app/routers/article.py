from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from app.database import get_session
from app.models import Article
from app.service import ArticleService
from app.schema import PageResponse

router = APIRouter()

class ArticleCreate(BaseModel):
    title: str
    cover_img: str
    content: Optional[str] = None
    category_id: int
    user_id: int
    is_public: bool = True
    is_recommended: bool = False

class ArticleOut(BaseModel):
    slug: str
    cover_img: str
    title: str
    category_id: int
    user_id: int
    view_count: int
    is_public: bool
    is_recommended: bool
    create_at: datetime

    class Config:
        from_attributes = True

class ArticleDetailOut(BaseModel):
    slug: str
    cover_img: str
    title: str
    content: Optional[str]
    category_id: int
    user_id: int
    view_count: int
    is_public: bool
    is_recommended: bool
    create_at: datetime

    class Config:
        from_attributes = True

@router.post("/", response_model=ArticleDetailOut, status_code=201)
async def create_article(
    article_in: ArticleCreate,
    session: AsyncSession = Depends(get_session)
):
    service = ArticleService(session)
    article = Article(**article_in.model_dump())
    created = await service.create(article)
    return ArticleDetailOut.model_validate(created)

@router.get("/latest", response_model=PageResponse[ArticleOut])
async def get_latest_article(
    limit: int = Query(default=3, ge=1, description='最近新闻数量'),
    session: AsyncSession = Depends(get_session)
):
    service = ArticleService(session)
    result = await service.get_latest(limit)
    return PageResponse(
        data=[ArticleOut.model_validate(a) for a in result.data],
        total=result.total,
        page=result.page,
        page_size=result.page_size
    )

@router.get("/recommended", response_model=PageResponse[ArticleOut])
async def get_recommended_article(
    limit: int = Query(default=3, ge=1, description='推荐新闻数量'),
    session: AsyncSession = Depends(get_session)
):
    service = ArticleService(session)
    result = await service.get_recommended(limit)
    return PageResponse(
        data=[ArticleOut.model_validate(a) for a in result.data],
        total=result.total,
        page=result.page,
        page_size=result.page_size
    )

@router.get("/detail/{slug}", response_model=ArticleDetailOut)
async def get_article_detail(
    slug: str,
    session: AsyncSession = Depends(get_session)
):
    service = ArticleService(session)
    article = await service.get_detail_by_slug(slug)
    if article is None:
        raise HTTPException(status_code=404, detail="文章不存在")
    return ArticleDetailOut.model_validate(article)
