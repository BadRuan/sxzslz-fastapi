from typing import List, Optional, Tuple
from sqlalchemy import exists
from sqlalchemy.orm import selectinload
from sqlmodel import select, func, desc, update
from sqlmodel.ext.asyncio.session import AsyncSession
from app.model import Article, ArticleCategory, Category


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
        )

    async def get_by_slug(self, slug: str, include_deleted: bool = False) -> Optional[Article]:
        stmt = select(Article).where(Article.slug == slug)
        if not include_deleted:
            stmt = stmt.where(Article.is_deleted == False)  # noqa: E712
        result = await self.session.exec(self._with_relations(stmt))
        return result.first()

    async def list_paginated(
        self,
        page: int,
        page_size: int,
        category_id: Optional[int] = None,
        user_id: Optional[int] = None,
        is_deleted: bool = False,
    ) -> Tuple[List[Article], int]:
        """is_deleted=False 只返回未删除文章（默认前台/后台列表）；
        is_deleted=True 只返回已删除文章（后台回收站）"""
        base = select(Article).where(Article.is_deleted == is_deleted)
        if user_id is not None:
            base = base.where(Article.user_id == user_id)
        if category_id is not None:
            # 查询仅走二级分类：精确匹配关联，不做一级分类子树聚合
            related = (
                select(ArticleCategory.article_id)
                .where(
                    ArticleCategory.article_id == Article.id,
                    ArticleCategory.category_id == category_id,
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
                Category.id.in_(category_ids),  # type: ignore
            )
        )).all()
        if len(categories) != len(set(category_ids)):
            raise ValueError("存在无效的分类")
        for category in categories:
            if category.parent_id == 0:
                raise ValueError("文章仅支持关联二级分类")
        return list(categories)

    async def create(
        self,
        *,
        title: str,
        content: Optional[str],
        cover_img_slug: Optional[str],
        is_recommended: bool,
        user_id: int,
        category_ids: List[int],
    ) -> Article:
        article = Article(
            title=title,
            content=content,
            cover_img_slug=cover_img_slug,
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
        # 显式传 null 视为清空全部分类；先解析、最终统一赋值
        has_categories = "category_ids" in fields
        new_categories = await self._resolve_categories(
            fields.pop("category_ids") or []
        ) if has_categories else []
        # 先校验后赋值，避免中途抛错留下脏对象
        for key, value in fields.items():
            if value is None and key not in self.NULLABLE_FIELDS:
                raise ValueError(f"字段 {key} 不能为空")
        for key, value in fields.items():
            setattr(article, key, value)
        if has_categories:
            article.categories = new_categories
        await self.session.flush()
        return article

    async def increment_like(self, slug: str) -> Optional[int]:
        """匿名点赞：原子自增 like_count，返回最新计数；文章不存在（或已删除）返回 None"""
        result = await self.session.execute(
            update(Article)
            .where(Article.slug == slug, Article.is_deleted == False)  # noqa: E712
            .values(like_count=Article.like_count + 1)
        )
        if result.rowcount == 0:
            return None
        count = (await self.session.exec(
            select(Article.like_count).where(Article.slug == slug)
        )).one()
        return int(count)

    async def increment_view(self, slug: str) -> Optional[int]:
        """浏览量：原子自增 view_count，返回最新计数；文章不存在（或已删除）返回 None"""
        result = await self.session.execute(
            update(Article)
            .where(Article.slug == slug, Article.is_deleted == False)  # noqa: E712
            .values(view_count=Article.view_count + 1)
        )
        if result.rowcount == 0:
            return None
        count = (await self.session.exec(
            select(Article.view_count).where(Article.slug == slug)
        )).one()
        return int(count)

    async def soft_delete(self, slug: str) -> bool:
        article = await self.get_by_slug(slug)
        if article is None:
            return False
        article.is_deleted = True
        await self.session.flush()
        return True

    async def restore(self, slug: str) -> Optional[Article]:
        """恢复软删除文章（幂等：未删除时直接返回原文章）；不存在返回 None"""
        article = await self.get_by_slug(slug, include_deleted=True)
        if article is None:
            return None
        if article.is_deleted:
            article.is_deleted = False
            await self.session.flush()
        return article
