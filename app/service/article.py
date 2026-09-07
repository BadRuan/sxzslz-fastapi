from typing import Optional, List
from sqlmodel.ext.asyncio.session import AsyncSession
from app.model import Article, Category
from app.dao import ArticleCrud, CategoryCrud, UserCrud, ArticleCategoryCrud
from app.schema import ArticleDetailOut, ArticleOut, PageResponse, CategoryTree


class ArticleService:
    def __init__(self, session: AsyncSession) -> None:
        self.crud = ArticleCrud(session)
        self.user_crud = UserCrud(session)
        self.category_curd = CategoryCrud(session)
        self.article_category_crud = ArticleCategoryCrud(session)

    async def get_article(self, article_slug: str) -> Optional[ArticleDetailOut]:
        article: Optional[ArticleDetailOut] = await self.crud.query_detail_by_slug(article_slug)
        if article is None:
            return None
        else:
            await self.crud.increase_view_count(article_slug)
            # 补充用户信息
            article.user = await self.user_crud.get_by_user_id(article.user_id)
            # 补充面包屑信息
            article.primary_category = await self.article_category_crud.query_primary_by_article_id(article.id)
            if article.primary_category is not None:
                c = await self.category_curd.query_by_category_id(article.primary_category.category_id)
                if c:
                    article.primary_category.category_name = c.name
            return article
            
    async def query_category_article(self, category_id: int, page: int = 1, limit: int = 10) -> PageResponse:
        if category_id <= 0:
            return PageResponse(
                data=[], total=0, page=0, page_size=0, has_next=False
            )
        else:
            offset = (page - 1) * limit
            articles: List[Article] = await self.crud.query_category_article(category_id, offset, limit)
            raw_categories: List[Category] = await self.category_curd.query_raw_all()
            category: Optional[CategoryTree] = None
            for c in raw_categories:
                if c.id == category_id:
                    category = CategoryTree.model_validate(c)
            taget_articles: List[ArticleOut] = []
            
            for article in articles:
                a: ArticleOut = ArticleOut.model_validate(article)
                a.category = category
                a.user = await self.user_crud.get_by_user_id(article.user_id)
                taget_articles.append(a)
            total_count: int = await self.crud.count_category_article(category_id)
            return PageResponse(
                data=taget_articles, 
                total= total_count, 
                page=page, 
                page_size=limit, 
                has_next= (offset + limit) < total_count
            )
            
    async def query_recommended_article(self, limit: int = 10) -> List[ArticleOut]:
        articles: List[Article] = await self.crud.query_recommended_article(limit)
        recommend_article: List[ArticleOut] = []
        categries: List[Category] = await self.category_curd.query_raw_all()
        for a in articles:
            target: ArticleOut = ArticleOut.model_validate(a)
            article_category = await self.article_category_crud.query_primary_by_article_id(a.id)
            if article_category:
                for c in categries:
                    if c.id == article_category.category_id:    
                        target.category = CategoryTree.model_validate(c)
                        target.user = await self.user_crud.get_by_user_id(a.user_id)
            recommend_article.append(target)
        return recommend_article