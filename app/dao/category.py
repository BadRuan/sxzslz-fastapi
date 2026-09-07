from typing import List, Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, asc
from app.model import Category
from app.schema import CategoryTree


def build_category_tree(categories: List[Category]) -> List[CategoryTree]:
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
    
    async def query_raw_all(self) -> List[Category]:
            stmt = (
                select(Category)
                .order_by(asc(Category.sort), asc(Category.id))
            )
            result = await self.session.exec(stmt)
            return list(result.all())
    
    # 输出分类树
    async def query_all(self) -> List[CategoryTree]:
        stmt = (
            select(Category)
            .order_by(asc(Category.sort), asc(Category.id))
        )
        result = await self.session.exec(stmt)
        roots = build_category_tree(list(result.all()))
        return roots
    
    async def query_by_category_id(self, id: int) -> Optional[CategoryTree]:
        stmt = (
            select(Category)
            .where(Category.id == id)
        )
        result = await self.session.exec(stmt)
        category = result.first()
        if category is None:
            return None
        else:
            return CategoryTree.model_validate(category)
            