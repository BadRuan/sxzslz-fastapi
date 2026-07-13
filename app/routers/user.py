from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession
from pydantic import BaseModel
from app.database import get_session
from app.service import UserService
from app.schema import PageResponse

router = APIRouter()

class UserOut(BaseModel):
    id: int
    nickname: str

    class Config:
        from_attributes = True

@router.get("/", response_model=PageResponse[UserOut])
async def get_all(
    page: int = Query(default=1, ge=1, description='页码'),
    page_size: int = Query(default=10, ge=1, le=100, description='每页条数'),
    session: AsyncSession = Depends(get_session)
):
    """获取所有用户"""
    service = UserService(session)
    result = await service.list_by_page(page, page_size)
    return PageResponse(
        data=[UserOut.model_validate(u) for u in result.data],
        total=result.total,
        page=result.page,
        page_size=result.page_size
    )
