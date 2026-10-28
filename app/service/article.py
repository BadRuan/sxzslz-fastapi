from typing import Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from app.settings import settings
from app.dao import ArticleCrud
from app.schema import (
    ArticleBatchCategoryIn,
    ArticleBatchCategoryOut,
    ArticleCreate,
    ArticleUpdate,
    ArticleOut,
    ArticleDetailOut,
    PageResponse,
    page_response,
)


class ArticleService:
    def __init__(self, session: AsyncSession) -> None:
        self.crud = ArticleCrud(session)

    async def create(self, data: ArticleCreate, user_id: Optional[int] = None) -> ArticleDetailOut:
        article = await self.crud.create(
            title=data.title,
            content=data.content,
            cover_img_slug=data.cover_img_slug,
            is_recommended=data.is_recommended,
            # API 层传当前登录用户；直接调 service 时退化为默认作者
            user_id=user_id if user_id is not None else settings.DEFAULT_USER_ID,
            category_ids=data.category_ids,
            create_at=data.create_at,
        )
        article = await self.crud.get_by_slug(article.slug)
        return ArticleDetailOut.model_validate(article)

    async def list_paginated(
        self,
        page: int,
        page_size: int,
        category_id: Optional[int] = None,
        user_id: Optional[int] = None,
        is_deleted: bool = False,
    ) -> PageResponse[ArticleOut]:
        """is_deleted=True 走后台回收站（只返回已删除文章）"""
        items, total = await self.crud.list_paginated(
            page, page_size, category_id, user_id, is_deleted
        )
        return page_response(
            [ArticleOut.model_validate(a) for a in items], total, page, page_size
        )

    async def find_by_slug(self, slug: str) -> Optional[ArticleDetailOut]:
        """只读查询（权限校验 / 改前定位用）；不自增 view_count"""
        article = await self.crud.get_by_slug(slug)
        if article is None:
            return None
        return ArticleDetailOut.model_validate(article)

    async def get_by_slug(self, slug: str) -> Optional[ArticleDetailOut]:
        article = await self.crud.get_by_slug(slug)
        if article is None:
            return None
        return ArticleDetailOut.model_validate(article)

    async def view(self, slug: str) -> Optional[ArticleDetailOut]:
        """详情访问：公开匿名，查文章并原子自增 view_count（已删/不存在返回 None，不计数）"""
        article = await self.crud.get_by_slug(slug)
        if article is None:
            return None
        view_count = await self.crud.increment_view(slug)
        if view_count is None:
            return None
        out = ArticleDetailOut.model_validate(article)
        # ORM 实例未感知裸 UPDATE，用自增后的计数覆盖
        out.view_count = view_count
        return out

    async def update(
        self,
        slug: str,
        data: ArticleUpdate,
        *,
        allow_admin_fields: bool = False,
    ) -> Optional[ArticleDetailOut]:
        """allow_admin_fields=False（普通用户）时剥离 user_id / create_at，其余字段照常更新"""
        fields = data.model_dump(exclude_unset=True)
        if not allow_admin_fields:
            fields.pop("user_id", None)
            fields.pop("create_at", None)
        article = await self.crud.update(slug, **fields)
        if article is None:
            return None
        article = await self.crud.get_by_slug(slug)
        return ArticleDetailOut.model_validate(article)

    async def delete(self, slug: str) -> bool:
        return await self.crud.soft_delete(slug)

    async def batch_category(self, data: ArticleBatchCategoryIn) -> ArticleBatchCategoryOut:
        """批量加入/移出分类；分类无效或文章不存在抛 ServiceError（→400）"""
        affected = await self.crud.batch_apply_category(
            data.slugs, data.category_id, data.mode
        )
        return ArticleBatchCategoryOut(affected=affected)

    async def restore(self, slug: str) -> Optional[ArticleDetailOut]:
        """恢复回收站文章；不存在返回 None"""
        article = await self.crud.restore(slug)
        if article is None:
            return None
        return ArticleDetailOut.model_validate(article)

    async def like(self, slug: str) -> Optional[int]:
        """匿名点赞，返回自增后的 like_count；文章不存在返回 None"""
        return await self.crud.increment_like(slug)
