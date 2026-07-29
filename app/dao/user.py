from typing import List
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from argon2 import PasswordHasher
from app.model import User

ph = PasswordHasher(
    time_cost=3,       # 迭代次数
    memory_cost=65536, # 内存成本 (64 MB)
    parallelism=4      # 并行线程数
)

class UserCrud:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> List[User]:
        data_stmt = (
            select(User)
            .order_by(User.id)  # type: ignore[arg-type]
        )
        result = await self.session.exec(data_stmt)
        return list(result.all())