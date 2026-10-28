from typing import List, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.dao import UserCrud
from app.errors import ServiceError
from app.model import User
from app.schema import PasswordResetOut, UserCreate, UserOut
from app.settings import settings


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.crud = UserCrud(session)

    async def get_all(self) -> List[UserOut]:
        user_list: List[User] = await self.crud.get_all()
        return [UserOut.model_validate(u) for u in user_list]

    async def get_by_id(self, user_id: int) -> Optional[User]:
        return await self.crud.get_by_id(user_id)

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

    async def create(self, data: UserCreate) -> UserOut:
        """创建普通账户（仅超管调用）：用户名 / 昵称唯一；密码缺省 abc123"""
        if await self.crud.get_by_username(data.username) is not None:
            raise ServiceError("用户名已存在")
        if await self.crud.get_by_nickname(data.nickname) is not None:
            raise ServiceError("昵称已存在")
        user = User.create_user(
            username=data.username,
            nickname=data.nickname,
            password=data.password or settings.DEFAULT_USER_PASSWORD,
            is_superuser=False,
        )
        await self.crud.add(user)
        return UserOut.model_validate(user)

    async def reset_password(self, user: User) -> PasswordResetOut:
        """重置普通账户密码为默认密码（脏对象随请求结束 commit）"""
        user.set_password(settings.DEFAULT_USER_PASSWORD)
        return PasswordResetOut(
            detail=f"密码已重置为 {settings.DEFAULT_USER_PASSWORD}"
        )

    async def delete(self, user: User) -> None:
        """硬删除账户；其文章 / 上传文件保留（user 关联自然为空）"""
        await self.crud.delete(user)
