from typing import Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from app.model import ArticleCategory
from app.schema import ArticleCategoryOut


class ArticleCategoryCrud:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
    
    async def query_primary_by_article_id(self, article_id: int ) -> Optional[ArticleCategoryOut]:
        stmt = (
            select(ArticleCategory)
            .where(ArticleCategory.article_id == article_id, ArticleCategory.is_primary == 1)
        )
        result = await self.session.exec(stmt)
        return ArticleCategoryOut.model_validate(result.first())