from typing import List
from sqlmodel.ext.asyncio.session import AsyncSession
from app.model import Category
from app.dao import CategoryCrud


class CategoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.crud = CategoryCrud(session)
    
    async def list_all(self) -> List[Category]:
        return await self.crud.list_all()
    