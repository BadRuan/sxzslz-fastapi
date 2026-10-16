from typing import List
from sqlmodel.ext.asyncio.session import AsyncSession
from app.model import User
from app.dao import UserCrud
from app.schema import UserOut


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.crud = UserCrud(session)

    async def get_all(self) -> List[UserOut]:
        user_list: List[User] = await self.crud.get_all()
        user_out_list: List[UserOut] = []
        for u in user_list:
            user_out_list.append(UserOut.model_validate(u))
        return user_out_list