from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.dao.file import FileCrud
from app.model import Image


class ImageCrud(FileCrud[Image]):
    """image 表：分页按 id 倒序（最新在前）"""

    model = Image
    order_by_field = "id"

    async def get_by_md5(self, md5: str) -> Image | None:
        stmt = self._with_user(select(self.model).where(self.model.md5 == md5))
        result = await self.session.exec(stmt)
        return result.first()
