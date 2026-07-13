from sqlmodel.ext.asyncio.session import AsyncSession
from app.dao import CategoryCrud
from app.schema import PageResponse


class CategoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.crud = CategoryCrud(session)
    
    async def get_all(self) -> PageResponse:
        return await self.crud.get_all()
    