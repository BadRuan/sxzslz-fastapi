from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from app.models import Category
from app.schema import PageResponse


class CategoryCrud:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_all(self) -> PageResponse:
        stmt = (
            select(Category)
            .order_by(Category.id)
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
    
