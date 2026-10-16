from typing import List, Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, asc
from app.model import Category
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

    async def get_active_all(self) -> List[Category]:
        stmt = (
            select(Category)
            .where(Category.is_deleted == False)  # noqa: E712
            .order_by(asc(Category.sort), asc(Category.id))
        )
        result = await self.session.exec(stmt)
        return list(result.all())

    # 输出分类树（不含已删除）
    async def get_tree_all(self) -> List[CategoryTree]:
        return _build_category_tree(await self.get_active_all())

    async def get_raw_by_id(self, category_id: int) -> Optional[Category]:
        stmt = select(Category).where(Category.id == category_id)
        result = await self.session.exec(stmt)
        return result.first()

    async def get_by_id(self, category_id: int) -> Optional[CategoryTree]:
        category = await self.get_raw_by_id(category_id)
        if category is None or category.is_deleted:
            return None
        return CategoryTree.model_validate(category)

    async def get_by_slug(self, slug: str) -> Optional[Category]:
        stmt = select(Category).where(
            Category.slug == slug,
            Category.is_deleted == False,  # noqa: E712
        )
        result = await self.session.exec(stmt)
        return result.first()

    async def get_by_name(self, name: str) -> Optional[Category]:
        stmt = select(Category).where(
            Category.name == name,
            Category.is_deleted == False,  # noqa: E712
        )
        result = await self.session.exec(stmt)
        return result.first()

    async def create(self, *, name: str, slug: str, parent_id: int, sort: int) -> Category:
        parent = None
        if parent_id:
            parent = await self.get_raw_by_id(parent_id)
            if parent is None or parent.is_deleted:
                raise ValueError("父分类不存在")
        category = Category(
            name=name, slug=slug, parent_id=parent_id, sort=sort, path="", level=1
        )
        self.session.add(category)
        await self.session.flush()
        if parent:
            category.level = parent.level + 1
            category.path = f"{parent.path}{category.id}/"
        else:
            category.path = f"/{category.id}/"
        await self.session.flush()
        return category

    async def update(
        self,
        category_id: int,
        *,
        name: Optional[str] = None,
        slug: Optional[str] = None,
        parent_id: Optional[int] = None,
        sort: Optional[int] = None,
    ) -> Optional[Category]:
        category = await self.get_raw_by_id(category_id)
        if category is None or category.is_deleted:
            return None
        if name is not None:
            category.name = name
        if slug is not None:
            category.slug = slug
        if sort is not None:
            category.sort = sort
        if parent_id is not None and parent_id != category.parent_id:
            await self._move(category, parent_id)
        await self.session.flush()
        return category

    async def _move(self, category: Category, new_parent_id: int) -> None:
        if new_parent_id == 0:
            new_parent = None
        else:
            new_parent = await self.get_raw_by_id(new_parent_id)
            if new_parent is None or new_parent.is_deleted:
                raise ValueError("父分类不存在")
            if new_parent.id == category.id or new_parent.path.startswith(category.path):
                raise ValueError("不能移动到自身或其子分类下")
        old_path = category.path
        if new_parent is None:
            category.parent_id = 0
            category.level = 1
            category.path = f"/{category.id}/"
        else:
            category.parent_id = new_parent.id
            category.level = new_parent.level + 1
            category.path = f"{new_parent.path}{category.id}/"
        # 同步更新所有后代的路径与层级
        descendants = (await self.session.exec(
            select(Category).where(
                Category.path.like(f"{old_path}%"),
                Category.id != category.id,
            )
        )).all()
        for item in descendants:
            item.path = category.path + item.path[len(old_path):]
            item.level = item.path.count("/") - 1

    async def soft_delete(self, category_id: int) -> bool:
        category = await self.get_raw_by_id(category_id)
        if category is None or category.is_deleted:
            return False
        # 级联软删整棵子树，保证分类树接口与平铺接口行为一致
        descendants = (await self.session.exec(
            select(Category).where(
                Category.path.like(f"{category.path}%"),
                Category.is_deleted == False,  # noqa: E712
            )
        )).all()
        for item in descendants:
            item.is_deleted = True
        await self.session.flush()
        return True
