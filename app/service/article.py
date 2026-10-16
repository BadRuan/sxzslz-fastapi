from typing import Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from app.settings import settings
from app.dao import ArticleCrud
from app.schema import ArticleCreate, ArticleUpdate, ArticleOut, ArticleDetailOut, PageResponse


class ArticleService:
    def __init__(self, session: AsyncSession) -> None:
        self.crud = ArticleCrud(session)

    async def create(self, data: ArticleCreate) -> ArticleDetailOut:
        article = await self.crud.create(
            title=data.title,
            content=data.content,
            cover_img_slug=data.cover_img_slug,
            is_hidden=data.is_hidden,
            is_recommended=data.is_recommended,
            user_id=settings.DEFAULT_USER_ID,
            category_ids=data.category_ids,
        )
        article = await self.crud.get_by_id(article.id)
        return ArticleDetailOut.model_validate(article)

    async def list_paginated(
        self, page: int, page_size: int, category_id: Optional[int] = None
    ) -> PageResponse[ArticleOut]:
        items, total = await self.crud.list_paginated(page, page_size, category_id)
        data = [ArticleOut.model_validate(a) for a in items]
        return PageResponse(
            data=data,
            total=total,
            page=page,
            page_size=page_size,
            has_next=page * page_size < total,
        )

    async def get(self, article_id: int) -> Optional[ArticleDetailOut]:
        article = await self.crud.get_by_id(article_id)
        if article is None:
            return None
        return ArticleDetailOut.model_validate(article)

    async def update(self, article_id: int, data: ArticleUpdate) -> Optional[ArticleDetailOut]:
        article = await self.crud.update(article_id, **data.model_dump(exclude_unset=True))
        if article is None:
            return None
        article = await self.crud.get_by_id(article_id)
        return ArticleDetailOut.model_validate(article)

    async def delete(self, article_id: int) -> bool:
        return await self.crud.soft_delete(article_id)
