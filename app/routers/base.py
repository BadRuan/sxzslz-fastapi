from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from app.database import get_session
from app.dao import CategoryCrud
from app.service import UserService


router = APIRouter()


@router.get("/base/")
async def get_category(session: AsyncSession = Depends(get_session)):
    category_dao = CategoryCrud(session)
    user_service = UserService(session)
    
    categories = await category_dao.get_tree_all()
    users = await user_service.get_all()
    
    return {
        "category": categories,
        "user": users
    }
