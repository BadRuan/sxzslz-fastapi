from typing import Optional, List
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, update, desc, func
from app.model import Article, Category, ArticleCategory
from app.schema import ArticleDetailOut


class ArticleCrud:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # 查询某分类（含所有子孙分类）下的文章总数
    async def count_category_article(self, category_id: int) -> int:
            subquery = select(Category.path).where(Category.id == category_id)
            stmt = (
                select(func.count(Article.id)) # type: ignore[arg-type]
                .join(ArticleCategory, Article.id == ArticleCategory.article_id)  # INNER JOIN article_category # type: ignore
                .join(Category, ArticleCategory.category_id == Category.id)       # INNER JOIN category # type: ignore
                .where(
                    Category.path.startswith(subquery), # type: ignore
                    Article.status == 1
                )
            )
            return await self.session.scalar(stmt) or 0
    
    # 查询某分类（含所有子孙分类）下的文章
    async def query_category_article(self, category_id: int, skip: int = 0, limit: int = 10) -> List[Article]:
        subquery = select(Category.path).where(Category.id == category_id)
        stmt = (
            select(Article)
            .join(ArticleCategory, Article.id == ArticleCategory.article_id)  # INNER JOIN article_category # type: ignore
            .join(Category, ArticleCategory.category_id == Category.id)       # INNER JOIN category # type: ignore
            .where(
                Category.path.startswith(subquery), # type: ignore
                Article.status == 1
            )
            .order_by(
                desc(Article.create_at)
            )
            .offset(skip) 
            .limit(limit)
        )
        result = await self.session.exec(stmt)
        return list(result.unique().all())

    async def query_recommended_article(self, limit: int) -> List[Article]:  
        stmt = (
            select(Article)
            .join(ArticleCategory, Article.id == ArticleCategory.article_id)  # INNER JOIN article_category # type: ignore
            .join(Category, ArticleCategory.category_id == Category.id)       # INNER JOIN category # type: ignore
            .where(Article.status == 1)
            .order_by(desc(Article.create_at)) 
            .limit(limit)
        )
        result = await self.session.exec(stmt)
        return list(result.unique().all())

    async def increase_view_count(self, slug: str) -> None:
        await self.session.exec(
            update(Article)
            .where(Article.slug == slug) # type: ignore
            .values(view_count=Article.view_count + 1)
        )

    async def query_detail_by_slug(self, slug: str) -> Optional[ArticleDetailOut]:
        article_stmt = (
            select(Article)
            .where(Article.slug == slug)
        )
        result = await self.session.exec(article_stmt)
        return ArticleDetailOut.model_validate(result.first())
    