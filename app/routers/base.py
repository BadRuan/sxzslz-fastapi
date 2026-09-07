from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from app.database import get_session
from app.dao import CategoryCrud


router = APIRouter()


@router.get("/category/")
async def get_category(session: AsyncSession = Depends(get_session)):
    category_dao = CategoryCrud(session)
    categories = await category_dao.query_all()
    return categories
    