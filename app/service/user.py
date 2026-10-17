from typing import List, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.dao import UserCrud
from app.model import User
from app.schema import UserOut


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.crud = UserCrud(session)

    async def get_all(self) -> List[UserOut]:
        user_list: List[User] = await self.crud.get_all()
        return [UserOut.model_validate(u) for u in user_list]

    async def get_by_username(self, username: str) -> Optional[User]:
        return await self.crud.get_by_username(username)