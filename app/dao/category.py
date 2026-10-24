from typing import List, Optional
from sqlmodel import select, asc
from sqlmodel.ext.asyncio.session import AsyncSession
from app.model import ArticleCategory, Category
from app.schema import CategoryTree


def _build_category_tree(categories: List[Category]) -> List[CategoryTree]:
    node_map = {item.id: CategoryTree.model_validate(item) for item in categories}
    roots = []
    for item in categories:
        node = node_map[item.id]
        if item.parent_id == 0:
            roots.append(node)
        else:
            parent_node = node_map.get(item.parent_id)
            if parent_node:
                parent_node.children.append(node)
    return roots


class CategoryCrud:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_all(self) -> List[Category]:
        stmt = select(Category).order_by(asc(Category.sort), asc(Category.id))
        result = await self.session.exec(stmt)
        return list(result.all())

    # 输出分类树（一级 → 二级）
    async def get_tree_all(self) -> List[CategoryTree]:
        return _build_category_tree(await self.get_all())

    async def get_raw_by_id(self, category_id: int) -> Optional[Category]:
        stmt = select(Category).where(Category.id == category_id)
        result = await self.session.exec(stmt)
        return result.first()

    async def get_children(self, parent_id: int) -> List[Category]:
        stmt = select(Category).where(Category.parent_id == parent_id)
        result = await self.session.exec(stmt)
        return list(result.all())

    async def create(self, *, name: str, parent_id: int, sort: int) -> Category:
        if parent_id != 0:
            parent = await self.get_raw_by_id(parent_id)
            if parent is None:
                raise ValueError("父分类不存在")
            if parent.parent_id != 0:
                raise ValueError("仅支持二级分类，不能创建三级分类")
        category = Category(name=name, parent_id=parent_id, sort=sort)
        self.session.add(category)
        await self.session.flush()
        return category

    async def update(
        self,
        category_id: int,
        *,
        name: Optional[str] = None,
        parent_id: Optional[int] = None,
        sort: Optional[int] = None,
    ) -> Optional[Category]:
        category = await self.get_raw_by_id(category_id)
        if category is None:
            return None
        if name is not None:
            category.name = name
        if sort is not None:
            category.sort = sort
        if parent_id is not None and parent_id != category.parent_id:
            await self._reparent(category, parent_id)
        await self.session.flush()
        return category

    async def _reparent(self, category: Category, new_parent_id: int) -> None:
        """二级分类仅可改挂到另一个一级分类下；一级分类固定在顶层。"""
        if category.parent_id == 0:
            raise ValueError("一级分类不支持调整父级")
        if new_parent_id == 0:
            raise ValueError("仅支持二级分类，不能调整为一级分类")
        parent = await self.get_raw_by_id(new_parent_id)
        if parent is None:
            raise ValueError("父分类不存在")
        if parent.parent_id != 0:
            raise ValueError("父分类必须是一级分类")
        category.parent_id = parent.id

    async def delete(self, category_id: int) -> bool:
        """硬删除分类：级联删除子分类，并清理文章关联（业务层外键）。"""
        category = await self.get_raw_by_id(category_id)
        if category is None:
            return False
        ids = [category.id]
        ids.extend(c.id for c in await self.get_children(category.id))

        links = (await self.session.exec(
            select(ArticleCategory).where(ArticleCategory.category_id.in_(ids))  # type: ignore
        )).all()
        for link in links:
            await self.session.delete(link)
        for cid in ids:
            node = await self.get_raw_by_id(cid)
            if node is not None:
                await self.session.delete(node)
        await self.session.flush()
        return True
