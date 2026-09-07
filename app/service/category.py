from sqlmodel.ext.asyncio.session import AsyncSession
from app.dao import CategoryCrud


class CategoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.crud = CategoryCrud(session)
