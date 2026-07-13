from typing import Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func
from argon2 import PasswordHasher
from app.models import User
from app.schema import PageResponse

ph = PasswordHasher(
    time_cost=3,       # 迭代次数
    memory_cost=65536, # 内存成本 (64 MB)
    parallelism=4      # 并行线程数
)

class UserCrud:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_page(self, page: int, page_size: int) -> PageResponse:
        count_stmt = select(func.count(User.id)).select_from(User)  # type: ignore[arg-type]
        total = await self.session.exec(count_stmt)
        total_count: int = total.one()
        
        offset = (page - 1) * page_size
        
        data_stmt = (
            select(User)
            .offset(offset)
            .limit(page_size)
            .order_by(User.id)  # type: ignore[arg-type]
        )
        result = await self.session.exec(data_stmt)
        users = list(result.all())
        return PageResponse(
            data=users,
            total=total_count,
            page=page,
            page_size=page_size
        )
