from sqlmodel.ext.asyncio.session import AsyncSession
from app.dao import UserCrud
from app.schema import PageResponse


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.crud = UserCrud(session)
    
    async def list_by_page(self, page: int, page_size: int) -> PageResponse:
        return await self.crud.list_by_page(page, page_size)
    