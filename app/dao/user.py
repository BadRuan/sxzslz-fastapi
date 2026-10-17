from typing import List, Optional

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

    async def get_by_username(self, username: str) -> Optional[User]:
        stmt = select(User).where(User.username == username)
        result = await self.session.exec(stmt)
        return result.first()
