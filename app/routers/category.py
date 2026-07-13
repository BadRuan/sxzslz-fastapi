from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from app.database import get_session
from app.models import Category
from app.service import CategoryService
from app.schema import PageResponse

router = APIRouter()


@router.get("/", response_model=PageResponse[Category])
async def get_all(
    session: AsyncSession = Depends(get_session)
    ):
    service = CategoryService(session)
    categories = await service.get_all()
    return categories
