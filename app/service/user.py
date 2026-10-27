from typing import List, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.dao import UserCrud
from app.errors import ServiceError
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

    async def change_password(
        self, user: User, old_password: str, new_password: str
    ) -> None:
        """校验旧密码后改密；旧密码错误抛 ServiceError（→400）。
        user 来自 get_current_user（同请求 session），脏对象随请求结束自动 commit。"""
        if not user.check_password(old_password):
            raise ServiceError("原密码错误")
        user.set_password(new_password)