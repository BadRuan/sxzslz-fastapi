from typing import Optional
from datetime import datetime
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, desc, func, update
from app.models import Article
from app.schema import PageResponse


class ArticleCrud:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, article: Article) -> Article:
        self.session.add(article)
        await self.session.flush()
        return article

    async def get_latest(self, limit: int) -> PageResponse:
        stmt = (
            select(Article)
            .where(Article.is_public == True)  # type: ignore[arg-type]
            .order_by(desc(Article.create_at))
            .limit(limit)
        )
        result = await self.session.exec(stmt)
        return PageResponse(
            data=list(result.all()),
            total=limit,
            page=1,
            page_size=limit
            )

    async def get_recommended(self, limit: int) -> PageResponse:
        stmt = (
            select(Article)
            .where(Article.is_recommended == True, Article.is_public == True)  # type: ignore[arg-type]
            .order_by(desc(Article.create_at))
            .limit(limit)
        )
        result = await self.session.exec(stmt)
        return PageResponse(
            data=list(result.all()),
            total=limit,
            page=1,
            page_size=limit
            )

    async def get_detail_by_slug(self, article_slug: str) -> Optional[Article]:
        """根据 slug 获取文章详情"""
        stmt = (
            select(Article)
            .where(Article.slug == article_slug)  # type: ignore[arg-type]
        )
        result = await self.session.exec(stmt)
        return result.first()

    async def record_view(self, article_slug: str) -> None:
        """阅读量 +1"""
        await self.session.exec(
            update(Article)
            .where(Article.slug == article_slug)  # type: ignore[arg-type]
            .values(view_count=Article.view_count + 1)
        )

    async def get_total_count(self) -> int:
        return (await self.session.scalar(
            func.count(Article.id)  # type: ignore[arg-type]
        )) or 0

    async def get_monthly_count(self) -> int:
        """获取本月文章数"""
        now = datetime.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return (await self.session.scalar(
            select(func.count(Article.id))  # type: ignore[arg-type]
            .where(
                Article.create_at >= start_of_month  # type: ignore[arg-type]
            )
        )) or 0
