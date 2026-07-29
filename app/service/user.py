from typing import List
from sqlmodel.ext.asyncio.session import AsyncSession
from app.model import User
from app.dao import UserCrud



class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.crud = UserCrud(session)
    
    async def list_all(self) -> List[User]:
        return await self.crud.list_all()
    