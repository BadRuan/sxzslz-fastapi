from fastapi import APIRouter, Query, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from app.database import get_session
from app.dao import CategoryCrud
from app.service import ArticleService


router = APIRouter()

@router.get("/category")
@router.get("/category/")
async def category(session: AsyncSession = Depends(get_session)):
    category_dao = CategoryCrud(session)
    categories = await category_dao.query_all()
    return categories


@router.get("/detail/{slug}/")
@router.get("/detail/{slug}")
async def get_detail(slug: str, session: AsyncSession = Depends(get_session)):
    service = ArticleService(session)
    article = await service.get_article(slug)
    if article is None:
        raise HTTPException(status_code=404, detail="文章不存在")
    return article


@router.get("/list")
@router.get("/list/")
async def get_list(
    category_id: int = Query(default=1, ge=1, description='文章分类'),
    page: int = Query(default=1, ge=1, description='页码'),
    page_size: int = Query(default=30, ge=1, description='每页数量'), session: AsyncSession = Depends(get_session)
):
    service = ArticleService(session)
    result = await service.query_category_article(category_id, page, page_size)
    if result is None:
        raise HTTPException(status_code=404, detail="文章不存在")
    else:
        return result

@router.get("/recommended")
@router.get("/recommended/")
async def get_recommended(
    limit: int = Query(default=10, ge=1), session: AsyncSession = Depends(get_session)
):
    service = ArticleService(session)
    result = await service.query_recommended_article(limit)
    if result is None:
        raise HTTPException(status_code=404, detail="推荐不存在")
    else:
        return result