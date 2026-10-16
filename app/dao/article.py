from typing import List, Optional, Tuple
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, desc
from sqlalchemy.orm import selectinload
from app.model import Article, Category


class ArticleCrud:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _with_relations(stmt):
        return stmt.options(
            selectinload(Article.categories),  # type: ignore
            selectinload(Article.user),  # type: ignore
        )

    async def get_by_id(self, article_id: int) -> Optional[Article]:
        stmt = self._with_relations(
            select(Article).where(Article.id == article_id, Article.is_deleted == False)  # noqa: E712
        )
        result = await self.session.exec(stmt)
        return result.first()

    async def list_paginated(
        self, page: int, page_size: int, category_id: Optional[int] = None
    ) -> Tuple[List[Article], int]:
        base = select(Article).where(Article.is_deleted == False)  # noqa: E712
        if category_id is not None:
            cat_result = await self.session.exec(
                select(Category).where(Category.id == category_id)
            )
            category = cat_result.first()
            if category is None:
                return [], 0
            base = base.join(Article.categories).where(
                Category.path.like(f"{category.path}%")
            )

        count_stmt = select(func.count()).select_from(base.subquery())
        total: int = (await self.session.exec(count_stmt)).one()

        offset = (page - 1) * page_size
        data_stmt = self._with_relations(
            base.order_by(desc(Article.id)).offset(offset).limit(page_size)
        )
        result = await self.session.exec(data_stmt)
        return list(result.all()), total

    async def _resolve_categories(self, category_ids: List[int]) -> List[Category]:
        if not category_ids:
            return []
        categories = (await self.session.exec(
            select(Category).where(
                Category.id.in_(category_ids),
                Category.is_deleted == False,  # noqa: E712
            )
        )).all()
        if len(categories) != len(set(category_ids)):
            raise ValueError("存在无效的分类")
        return list(categories)

    async def create(
        self,
        *,
        title: str,
        content: Optional[str],
        cover_img_slug: Optional[str],
        is_hidden: bool,
        is_recommended: bool,
        user_id: int,
        category_ids: List[int],
    ) -> Article:
        article = Article(
            title=title,
            content=content,
            cover_img_slug=cover_img_slug,
            is_hidden=is_hidden,
            is_recommended=is_recommended,
            user_id=user_id,
        )
        article.categories = await self._resolve_categories(category_ids)
        self.session.add(article)
        await self.session.flush()
        return article

    async def update(self, article_id: int, **fields) -> Optional[Article]:
        article = await self.get_by_id(article_id)
        if article is None:
            return None
        category_ids = fields.pop("category_ids", None)
        for key, value in fields.items():
            if value is not None:
                setattr(article, key, value)
        if category_ids is not None:
            article.categories = await self._resolve_categories(category_ids)
        await self.session.flush()
        return article

    async def soft_delete(self, article_id: int) -> bool:
        article = await self.get_by_id(article_id)
        if article is None:
            return False
        article.is_deleted = True
        await self.session.flush()
        return True
