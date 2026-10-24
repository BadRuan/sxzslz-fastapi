from typing import List, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.dao import CategoryCrud
from app.schema import CategoryCreate, CategoryOut, CategoryTree, CategoryUpdate


class CategoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.crud = CategoryCrud(session)

    async def create(self, data: CategoryCreate) -> CategoryOut:
        # 分类名允许重名（不同父级下同名常见），不做唯一性拦截
        category = await self.crud.create(
            name=data.name, parent_id=data.parent_id, sort=data.sort
        )
        return CategoryOut.model_validate(category)

    async def list(self) -> List[CategoryOut]:
        categories = await self.crud.get_all()
        return [CategoryOut.model_validate(c) for c in categories]

    async def get_tree(self) -> List[CategoryTree]:
        return await self.crud.get_tree_all()

    async def get(self, category_id: int) -> Optional[CategoryOut]:
        category = await self.crud.get_raw_by_id(category_id)
        if category is None:
            return None
        return CategoryOut.model_validate(category)

    async def update(self, category_id: int, data: CategoryUpdate) -> Optional[CategoryOut]:
        category = await self.crud.update(
            category_id, **data.model_dump(exclude_unset=True)
        )
        if category is None:
            return None
        return CategoryOut.model_validate(category)

    async def delete(self, category_id: int) -> bool:
        return await self.crud.delete(category_id)
