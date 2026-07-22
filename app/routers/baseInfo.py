from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession
from pydantic import BaseModel
from app.models import Category
from app.database import get_session
from app.service import UserService, CategoryService
from app.schema import PageResponse

router = APIRouter()

class UserOut(BaseModel):
    id: int
    nickname: str

    class Config:
        from_attributes = True

# 返回所有分类和用户
@router.get("/user", response_model=PageResponse[UserOut])
async def get_all_user(
    page: int = Query(default=1, ge=1, description='页码'),
    page_size: int = Query(default=10, ge=1, le=100, description='每页条数'),
    session: AsyncSession = Depends(get_session)
):
    service = UserService(session)
    result = await service.list_by_page(page, page_size)
    return PageResponse(
        data=[UserOut.model_validate(u) for u in result.data],
        total=result.total,
        page=result.page,
        page_size=result.page_size
    )

@router.get("/category", response_model=PageResponse[Category])
async def get_all_categories(
    session: AsyncSession = Depends(get_session)
    ):
    service = CategoryService(session)
    categories = await service.get_all()
    return categories
