from typing import List, Optional
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession
from app.dao import CategoryCrud
from app.schema import CategoryCreate, CategoryUpdate, CategoryOut


class CategoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.crud = CategoryCrud(session)

    async def create(self, data: CategoryCreate) -> CategoryOut:
        if await self.crud.get_by_name(data.name):
            raise ValueError("分类名称已存在")
        if await self.crud.get_by_slug(data.slug):
            raise ValueError("分类 slug 已存在")
        try:
            category = await self.crud.create(
                name=data.name, slug=data.slug, parent_id=data.parent_id, sort=data.sort
            )
        except IntegrityError as e:
            # 校验通过后并发插入造成的唯一性冲突 → 400 而非 500
            raise ValueError("分类名称或 slug 已存在") from e
        return CategoryOut.model_validate(category)

    async def list(self) -> List[CategoryOut]:
        categories = await self.crud.get_active_all()
        return [CategoryOut.model_validate(c) for c in categories]

    async def get(self, category_id: int) -> Optional[CategoryOut]:
        category = await self.crud.get_raw_by_id(category_id)
        if category is None or category.is_deleted:
            return None
        return CategoryOut.model_validate(category)

    async def update(self, category_id: int, data: CategoryUpdate) -> Optional[CategoryOut]:
        if data.name is not None:
            existing = await self.crud.get_by_name(data.name)
            if existing is not None and existing.id != category_id:
                raise ValueError("分类名称已存在")
        if data.slug is not None:
            existing = await self.crud.get_by_slug(data.slug)
            if existing is not None and existing.id != category_id:
                raise ValueError("分类 slug 已存在")
        try:
            category = await self.crud.update(
                category_id, **data.model_dump(exclude_unset=True)
            )
        except IntegrityError as e:
            raise ValueError("分类名称或 slug 已存在") from e
        if category is None:
            return None
        return CategoryOut.model_validate(category)

    async def delete(self, category_id: int) -> bool:
        return await self.crud.soft_delete(category_id)
