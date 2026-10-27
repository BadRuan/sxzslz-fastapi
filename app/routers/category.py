from typing import List
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel.ext.asyncio.session import AsyncSession
from app.auth import get_current_user
from app.database import get_session
from app.model import User
from app.service import CategoryService
from app.schema import CategoryCreate, CategoryUpdate, CategoryOut


router = APIRouter()


@router.post("/", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    data: CategoryCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    # 业务校验失败（ServiceError）由全局 handler 统一转 400
    return await CategoryService(session).create(data)


@router.get("/", response_model=List[CategoryOut])
async def list_categories(session: AsyncSession = Depends(get_session)):
    service = CategoryService(session)
    return await service.list()


@router.get("/{category_id}", response_model=CategoryOut)
async def get_category(category_id: int, session: AsyncSession = Depends(get_session)):
    service = CategoryService(session)
    category = await service.get(category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在")
    return category


@router.patch("/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: int,
    data: CategoryUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    category = await CategoryService(session).update(category_id, data)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在")
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    service = CategoryService(session)
    if not await service.delete(category_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
