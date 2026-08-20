from typing import List
from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession
from app.schema import CountOut, ArticleOut, CategoryDetail
from app.database import get_session
from app.service.admin import AdminService

router = APIRouter()

@router.get("/", response_model=CountOut)
async def get_base(session: AsyncSession = Depends(get_session)):
    service = AdminService(session)
    result = await service.get_count_info()
    return result

@router.get("/latest/", response_model=List[ArticleOut])
@router.get("/latest", response_model=List[ArticleOut])
async def get_latest(limit: int = Query(default=20, ge=1, description='最近文章数量'),session: AsyncSession = Depends(get_session)):
    service = AdminService(session)
    result = await service.get_latest(limit)
    return result

@router.get("/category/", response_model=List[CategoryDetail])
@router.get("/category", response_model=List[CategoryDetail])
async def list_category_info(session: AsyncSession = Depends(get_session)):
    service = AdminService(session)
    result = await service.get_category_info()
    return result