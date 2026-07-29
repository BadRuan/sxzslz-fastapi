from typing import List
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func
from app.model import Category


class CategoryCrud:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> List[Category]:
        stmt = (
            select(Category).order_by(Category.id) # type: ignore[arg-type]
        )
        result = await self.session.exec(stmt)
        return list(result.all())

    async def get_total_count(self) -> int:
        return (await self.session.scalar(
            func.count(Category.id)  # type: ignore[arg-type]
        )) or 0