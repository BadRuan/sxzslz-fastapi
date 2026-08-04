from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from app.database import get_session
from app.service.admin import AdminService, CountOut

router = APIRouter()

@router.get("/", response_model=CountOut)
async def get_base(session: AsyncSession = Depends(get_session)):
    service = AdminService(session)
    result = await service.get_count_info()
    return result