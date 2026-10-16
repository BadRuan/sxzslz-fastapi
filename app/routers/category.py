from typing import List
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel.ext.asyncio.session import AsyncSession
from app.database import get_session
from app.service import CategoryService
from app.schema import CategoryCreate, CategoryUpdate, CategoryOut


router = APIRouter()


@router.post("/", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(data: CategoryCreate, session: AsyncSession = Depends(get_session)):
    service = CategoryService(session)
    try:
        return await service.create(data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


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
    category_id: int, data: CategoryUpdate, session: AsyncSession = Depends(get_session)
):
    service = CategoryService(session)
    try:
        category = await service.update(category_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在")
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: int, session: AsyncSession = Depends(get_session)):
    service = CategoryService(session)
    if not await service.delete(category_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
