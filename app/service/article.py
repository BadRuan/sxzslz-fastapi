from typing import Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from app.settings import settings
from app.dao import ArticleCrud
from app.schema import ArticleCreate, ArticleUpdate, ArticleOut, ArticleDetailOut, PageResponse


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
        data = [ArticleOut.model_validate(a) for a in items]
        return PageResponse(
            data=data,
            total=total,
            page=page,
            page_size=page_size,
            has_next=page * page_size < total,
        )

    async def get_by_slug(self, slug: str) -> Optional[ArticleDetailOut]:
        article = await self.crud.get_by_slug(slug)
        if article is None:
            return None
        return ArticleDetailOut.model_validate(article)

    async def update(self, slug: str, data: ArticleUpdate) -> Optional[ArticleDetailOut]:
        article = await self.crud.update(slug, **data.model_dump(exclude_unset=True))
        if article is None:
            return None
        article = await self.crud.get_by_slug(slug)
        return ArticleDetailOut.model_validate(article)

    async def delete(self, slug: str) -> bool:
        return await self.crud.soft_delete(slug)

    async def restore(self, slug: str) -> Optional[ArticleDetailOut]:
        """恢复回收站文章；不存在返回 None"""
        article = await self.crud.restore(slug)
        if article is None:
            return None
        return ArticleDetailOut.model_validate(article)

    async def like(self, slug: str) -> Optional[int]:
        """匿名点赞，返回自增后的 like_count；文章不存在返回 None"""
        return await self.crud.increment_like(slug)
