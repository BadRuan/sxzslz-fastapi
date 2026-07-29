from typing import Optional, List
from datetime import datetime
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, desc, func, update
from app.model import Article
from app.schema import PageResponse


class ArticleCrud:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, article: Article) -> Article:
        self.session.add(article)
        await self.session.flush()
        return article

    async def get_recommended(self, limit: int) -> List[Article]:
        stmt = (
            select(Article)
            .where(Article.is_recommended == True, Article.is_public == True)  # type: ignore[arg-type]
            .order_by(desc(Article.create_at))
            .limit(limit)
        )
        result = await self.session.exec(stmt)
        return list(result)

    async def get_articles_by_category(self, category_id: int, page: int = 1, page_size: int = 20) -> PageResponse:
        # 计算偏移量
        offset = (page - 1) * page_size

        # 查询总数
        count_stmt = (
            select(func.count(Article.id)) # type: ignore[arg-type]
            .where(
                Article.is_public == True,
                Article.category_id == category_id,
            )
        )
        total = await self.session.scalar(count_stmt) or 0

        # 查询分页数据
        data_stmt = (
            select(Article)
            .where(
                Article.is_public == True,
                Article.category_id == category_id,
            )
            .order_by(desc(Article.create_at))
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.exec(data_stmt)
        result_list = list(result.all())

        # 计算是否有下一页
        has_next = (offset + page_size) < total

        return PageResponse(
            data=result_list,
            total=total,
            page=page,
            page_size=page_size,
            has_next=has_next
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
