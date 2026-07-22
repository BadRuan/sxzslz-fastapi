from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func
from app.models import Category
from app.schema import PageResponse


class CategoryCrud:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_all(self) -> PageResponse:
        stmt = (
            select(Category)
        )
        result = await self.session.exec(stmt)
        data = list(result.all())
        length = len(data)
        return PageResponse(
            data=data,
            total=length,
            page=1,
            page_size=length
        )
    
    async def get_total_count(self) -> int:
        return (await self.session.scalar(
            func.count(Category.id)  # type: ignore[arg-type]
        )) or 0
