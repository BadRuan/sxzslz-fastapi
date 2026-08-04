from typing import List
from sqlmodel.ext.asyncio.session import AsyncSession
from app.model import Article
from app.schema import CountOut
from app.dao import UserCrud, ArticleCrud, ImageCrud, DocumentCrud


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.user_crud = UserCrud(session)
        self.aritcle_crud = ArticleCrud(session)
        self.image_crud = ImageCrud(session)
        self.document_curd = DocumentCrud(session)
        
    async def get_count_info(self) -> CountOut:
        return CountOut(
            total_article = await self.aritcle_crud.get_total_count(),
            month_article = await self.aritcle_crud.get_monthly_count(),
            image_count= await self.image_crud.get_total_count(),
            attachment_count= await self.document_curd.get_total_count(),
            user_count= await self.user_crud.get_total_count(),
            article_view= await self.aritcle_crud.get_total_view(),
            image_view= await self.image_crud.get_total_view(),
            download_count= await self.document_curd.get_download_count()
        )
        
    async def get_latest(self, limit: int) -> List[Article]:
        return await self.aritcle_crud.get_admin_latest(limit)