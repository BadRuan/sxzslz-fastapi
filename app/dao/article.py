from typing import List, Optional, Tuple
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, desc
from sqlalchemy import exists
from sqlalchemy.orm import selectinload, with_loader_criteria
from app.model import Article, Category, ArticleCategory


class ArticleCrud:
    # 数据库中允许为 NULL 的可空字段：显式传 null 表示清空
    NULLABLE_FIELDS = {"content", "cover_img_slug"}

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _with_relations(stmt):
        return stmt.options(
            selectinload(Article.categories),  # type: ignore
            selectinload(Article.user),  # type: ignore
            # 加载时过滤已软删分类（仅影响查询，不改写关联关系）
            with_loader_criteria(
                Category, lambda cls: cls.is_deleted == False  # noqa: E712
            ),
        )

    async def get_by_slug(self, slug: str) -> Optional[Article]:
        stmt = self._with_relations(
            select(Article).where(Article.slug == slug, Article.is_deleted == False)  # noqa: E712
        )
        result = await self.session.exec(stmt)
        return result.first()

    async def list_paginated(
        self, page: int, page_size: int, category_id: Optional[int] = None
    ) -> Tuple[List[Article], int]:
        base = select(Article).where(Article.is_deleted == False)  # noqa: E712
        if category_id is not None:
            cat_result = await self.session.exec(
                select(Category).where(
                    Category.id == category_id,
                    Category.is_deleted == False,  # noqa: E712
                )
            )
            category = cat_result.first()
            if category is None:
                return [], 0
            # EXISTS 避免多对多 join 产生重复行；只命中未删除的分类
            related = (
                select(ArticleCategory.article_id)
                .join(Category, Category.id == ArticleCategory.category_id) # type: ignore
                .where(
                    ArticleCategory.article_id == Article.id,
                    Category.path.like(f"{category.path}%"), # type: ignore
                    Category.is_deleted == False,  # noqa: E712
                )
            )
            base = base.where(exists(related))

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
                Category.id.in_(category_ids), # type: ignore
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

    async def update(self, slug: str, **fields) -> Optional[Article]:
        article = await self.get_by_slug(slug)
        if article is None:
            return None
        if "category_ids" in fields:
            # 显式传 null 视为清空全部分类
            article.categories = await self._resolve_categories(
                fields.pop("category_ids") or []
            )
        # 先校验后赋值，避免中途抛错留下脏对象
        for key, value in fields.items():
            if value is None and key not in self.NULLABLE_FIELDS:
                raise ValueError(f"字段 {key} 不能为空")
        for key, value in fields.items():
            setattr(article, key, value)
        await self.session.flush()
        return article

    async def soft_delete(self, slug: str) -> bool:
        article = await self.get_by_slug(slug)
        if article is None:
            return False
        article.is_deleted = True
        await self.session.flush()
        return True
