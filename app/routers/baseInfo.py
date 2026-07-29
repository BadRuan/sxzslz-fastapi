from typing import List
from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from pydantic import BaseModel
from app.database import get_session
from app.service import UserService, CategoryService

router = APIRouter()


class UserOut(BaseModel):
    id: int
    nickname: str

    class Config:
        from_attributes = True


class CategoryOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class BaseResponse(BaseModel):
    user: List[UserOut]
    category: List[CategoryOut]


# 返回所有分类和用户
@router.get("/base/", response_model=BaseResponse)
async def get_base(session: AsyncSession = Depends(get_session)):
    user_service = UserService(session)
    category_service = CategoryService(session)
    users = await user_service.list_all()
    categories = await category_service.list_all()

    # 手动转换用户数据，过滤掉敏感字段
    filtered_users = [
        {"id": user.id, "nickname": user.nickname}
        for user in users
    ]

    # 转换分类数据
    category_list = [
        {"id": cat.id, "name": cat.name}
        for cat in categories
    ]

    return {
        "user": filtered_users,
        "category": category_list
    }
