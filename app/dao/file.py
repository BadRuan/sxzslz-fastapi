from typing import Generic, List, Optional, Tuple, TypeVar

from sqlalchemy.orm import selectinload
from sqlmodel import SQLModel, desc, func, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

ModelT = TypeVar("ModelT", bound=SQLModel)


class FileCrud(Generic[ModelT]):
    """Image / Document 共用的文件记录 CRUD。

    子类只需声明 `model`（表模型）与 `order_by_field`（分页排序列名）。
    注意：排序列存列名字符串而非 ORM 列对象——列对象是描述符，
    挂在非 ORM 类上会在实例访问时触发 __get__ 报错。
    """

    model: type[ModelT]
    order_by_field: str

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @classmethod
    def _with_user(cls, stmt):
        """预加载上传者（业务层 user_id 关联），列表响应需要且避免异步懒加载"""
        return stmt.options(selectinload(cls.model.user))

    async def list_paginated(
        self, page: int, page_size: int, order_by_field: Optional[str] = None
    ) -> Tuple[List[ModelT], int]:
        """order_by_field 缺省时用子类声明的默认排序列"""
        order_column = getattr(self.model, order_by_field or self.order_by_field)
        total: int = (
            await self.session.exec(select(func.count()).select_from(self.model))
        ).one()
        offset = (page - 1) * page_size
        stmt = self._with_user(
            select(self.model)
            .offset(offset)
            .limit(page_size)
            .order_by(desc(order_column))
        )
        items: List[ModelT] = list((await self.session.exec(stmt)).all())
        return items, total

    async def get_by_slug(self, slugname: str) -> Optional[ModelT]:
        stmt = self._with_user(select(self.model).where(self.model.slug == slugname))
        result = await self.session.exec(stmt)
        return result.first()

    async def add(
        self, raw_filename: str, slug: str, mime_type: str, size: int, user_id: int
    ) -> ModelT:
        record = self.model(  # type: ignore[call-arg]
            raw_filename=raw_filename,
            slug=slug,
            mime_type=mime_type,
            size_bytes=size,
            user_id=user_id,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def record_view(self, slugname: str) -> Optional[int]:
        """原子自增 view，返回自增后的计数（UPDATE ... RETURNING 一次往返）"""
        result = await self.session.exec(
            update(self.model)
            .where(self.model.slug == slugname)  # type: ignore
            .values(view=self.model.view + 1)
            .returning(self.model.view)
        )
        row = result.first()
        return int(row[0]) if row is not None else None

    async def remove_by_slug(self, slugname: str) -> bool:
        record = await self.get_by_slug(slugname)
        if record is not None:
            await self.session.delete(record)
            return True
        return False
