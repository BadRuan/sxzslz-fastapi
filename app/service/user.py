from typing import List, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.dao import UserCrud
from app.errors import ServiceError
from app.model import User
from app.schema import PasswordResetOut, UserCreate, UserOut
from app.service.operation_log import OperationService
from app.settings import settings


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.crud = UserCrud(session)

    async def get_all(self) -> List[UserOut]:
        user_list: List[User] = await self.crud.get_all()
        return [UserOut.model_validate(u) for u in user_list]

    async def get_by_id(self, user_id: int) -> Optional[User]:
        return await self.crud.get_by_id(user_id)

    async def get_by_username(self, username: str) -> Optional[User]:
        return await self.crud.get_by_username(username)

    async def change_password(
        self,
        user: User,
        old_password: str,
        new_password: str,
        *,
        operator_id: Optional[int] = None,
        operator_name: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """校验旧密码后改密；旧密码错误抛 ServiceError（→400）。
        user 来自 get_current_user（同请求 session），脏对象随请求结束自动 commit。
        成功后记操作日志 update_account；写日志失败不影响主响应。"""
        if not user.check_password(old_password):
            await OperationService(self.session).log_operation(
                action="update_account",
                object_type="account",
                object_id=str(user.id),
                object_name=user.username,
                operator_id=operator_id,
                operator_name=operator_name,
                result="failed",
                message="原密码错误",
                client_ip=client_ip,
                user_agent=user_agent,
            )
            raise ServiceError("原密码错误")
        user.set_password(new_password)
        await OperationService(self.session).log_operation(
            action="update_account",
            object_type="account",
            object_id=str(user.id),
            object_name=user.username,
            operator_id=operator_id,
            operator_name=operator_name,
            result="success",
            client_ip=client_ip,
            user_agent=user_agent,
        )

    async def create(
        self,
        data: UserCreate,
        *,
        operator_id: Optional[int] = None,
        operator_name: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> UserOut:
        """创建普通账户（仅超管调用）：用户名 / 昵称唯一；密码缺省 abc123。
        成功后记操作日志 create_account；写日志失败不影响主响应。"""
        if await self.crud.get_by_username(data.username) is not None:
            await OperationService(self.session).log_operation(
                action="create_account",
                object_type="account",
                object_id=data.username,
                object_name=data.username,
                operator_id=operator_id,
                operator_name=operator_name,
                result="failed",
                message="用户名已存在",
                client_ip=client_ip,
                user_agent=user_agent,
            )
            raise ServiceError("用户名已存在")
        if await self.crud.get_by_nickname(data.nickname) is not None:
            await OperationService(self.session).log_operation(
                action="create_account",
                object_type="account",
                object_id=data.username,
                object_name=data.nickname,
                operator_id=operator_id,
                operator_name=operator_name,
                result="failed",
                message="昵称已存在",
                client_ip=client_ip,
                user_agent=user_agent,
            )
            raise ServiceError("昵称已存在")
        user = User.create_user(
            username=data.username,
            nickname=data.nickname,
            password=data.password or settings.DEFAULT_USER_PASSWORD,
            is_superuser=False,
        )
        await self.crud.add(user)
        await OperationService(self.session).log_operation(
            action="create_account",
            object_type="account",
            object_id=str(user.id),
            object_name=f"{data.username} / {data.nickname}",
            operator_id=operator_id,
            operator_name=operator_name,
            result="success",
            client_ip=client_ip,
            user_agent=user_agent,
        )
        return UserOut.model_validate(user)

    async def reset_password(
        self,
        user: User,
        *,
        operator_id: Optional[int] = None,
        operator_name: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> PasswordResetOut:
        """重置普通账户密码为默认密码（脏对象随请求结束 commit）。
        成功后记操作日志 update_account；写日志失败不影响主响应。"""
        user.set_password(settings.DEFAULT_USER_PASSWORD)
        await OperationService(self.session).log_operation(
            action="update_account",
            object_type="account",
            object_id=str(user.id),
            object_name=user.username,
            operator_id=operator_id,
            operator_name=operator_name,
            result="success",
            client_ip=client_ip,
            user_agent=user_agent,
        )
        return PasswordResetOut(
            detail=f"密码已重置为 {settings.DEFAULT_USER_PASSWORD}"
        )

    async def delete(
        self,
        user: User,
        *,
        operator_id: Optional[int] = None,
        operator_name: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """硬删除账户；其文章 / 上传文件保留（user 关联自然为空）。
        成功后记操作日志 delete_account；写日志失败不影响主响应。"""
        await self.crud.delete(user)
        await OperationService(self.session).log_operation(
            action="delete_account",
            object_type="account",
            object_id=str(user.id),
            object_name=user.username,
            operator_id=operator_id,
            operator_name=operator_name,
            result="success",
            client_ip=client_ip,
            user_agent=user_agent,
        )
