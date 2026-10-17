from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.schema import BaseInfoOut
from app.service import CategoryService, UserService

router = APIRouter()


@router.get("/base/", response_model=BaseInfoOut)
async def get_base_info(session: AsyncSession = Depends(get_session)):
    categories = await CategoryService(session).get_tree()
    users = await UserService(session).get_all()
    return BaseInfoOut(category=categories, user=users)
