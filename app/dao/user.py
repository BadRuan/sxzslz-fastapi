from typing import List, Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func
from argon2 import PasswordHasher
from app.model import User
from app.schema import UserOut

ph = PasswordHasher(
    time_cost=3,       # 迭代次数
    memory_cost=65536, # 内存成本 (64 MB)
    parallelism=4      # 并行线程数
)

class UserCrud:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all_user(self) -> List[User]:
        data_stmt = (
            select(User)
            .order_by(User.id)  # type: ignore[arg-type]
        )
        result = await self.session.exec(data_stmt)
        return list(result.all())
    
    async def get_total_count(self) -> int:
        return (await self.session.scalar(
            func.count(User.id)  # type: ignore[arg-type]
        )) or 0
    
    async def get_by_user_id(self, id: int) -> Optional[UserOut]:
        stmt = (
            select(User)
            .where(User.id == id)
        )
        result = await self.session.exec(stmt)
        return UserOut.model_validate(result.first())
