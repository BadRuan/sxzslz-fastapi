from typing import List, Optional

from sqlalchemy import delete as sa_delete
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.model import User


class UserCrud:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_all(self) -> List[User]:
        data_stmt = select(User).order_by(User.id)  # type: ignore[arg-type]
        result = await self.session.exec(data_stmt)
        return list(result.all())

    async def get_by_id(self, user_id: int) -> Optional[User]:
        return await self.session.get(User, user_id)

    async def get_by_username(self, username: str) -> Optional[User]:
        stmt = select(User).where(User.username == username)
        result = await self.session.exec(stmt)
        return result.first()

    async def get_by_nickname(self, nickname: str) -> Optional[User]:
        stmt = select(User).where(User.nickname == nickname)
        result = await self.session.exec(stmt)
        return result.first()

    async def add(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def delete(self, user: User) -> None:
        """删除账户行（Core DELETE，绕过 ORM 关系级联）。

        文章 / 图片 / 文档与用户仅业务关联、无数据库外键：若走 ORM 删除，
        SQLAlchemy 会加载关联集合并把其 user_id 置空（文章 user_id 非空 → 约束失败）。
        这里直接 DELETE 用户行，内容记录保留原 user_id，响应中作者关联自然为 null。
        """
        await self.session.exec(sa_delete(User).where(User.id == user.id))
        self.session.expunge(user)
        await self.session.flush()
