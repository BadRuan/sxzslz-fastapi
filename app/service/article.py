from typing import Optional, Tuple
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models import Article
from app.dao import ArticleCrud, CategoryCrud
from app.schema import PageResponse


class ArticleService:
    def __init__(self, session: AsyncSession) -> None:
        self.crud = ArticleCrud(session)
        self.category_curd = CategoryCrud(session)
        
    async def create(self, article: Article) -> Article:
        return await self.crud.create(article)
    
    async def get_recommended(self, limit: int) -> PageResponse:
        return await self.crud.get_recommended(limit)
    
    async def get_articles_by_category(self, category_id: int, page_size: int) -> PageResponse:  
        category_count: int = await self.category_curd.get_total_count()
        if category_id > category_count:
            return PageResponse(
            data=[],
            total=0,
            page=1,
            page_size=0
            )
        else:
            return await self.crud.get_articles_by_category(category_id, page_size)

    
    async def get_detail_by_slug(self, slug: str) -> Optional[Article]:
        article = await self.crud.get_detail_by_slug(slug)
        if article is not None:
            await self.crud.record_view(slug)
        return article
    
    async def get_count(self) -> Tuple:
        total_count: int = await self.crud.get_total_count()
        month_count: int = await self.crud.get_monthly_count()
        return total_count, month_count

    