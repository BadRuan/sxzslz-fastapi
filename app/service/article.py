from datetime import datetime, timedelta
from typing import Literal, Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from app.dao import ArticleCrud
from app.errors import ServiceError
from app.model import User
from app.schema import (
    ArticleBatchCategoryIn,
    ArticleBatchCategoryOut,
    ArticleCreate,
    ArticleInfiniteOut,
    ArticleUpdate,
    ArticleOut,
    ArticleSearchOut,
    ArticleStatsOut,
    ArticleStatsScope,
    ArticleDetailOut,
    PageResponse,
    SearchScope,
    decode_cursor,
    page_response,
)
from app.settings import settings
from app.service.operation_log import OperationService
from app.types import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.utils.search import build_snippet, matched_fields, split_terms


class ArticleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.crud = ArticleCrud(session)

    async def create(
        self,
        data: ArticleCreate,
        user_id: Optional[int] = None,
        *,
        operator_id: Optional[int] = None,
        operator_name: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ArticleDetailOut:
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
        await OperationService(self.session).log_operation(
            action="create_article",
            object_type="article",
            object_id=article.slug,
            object_name=data.title,
            operator_id=operator_id,
            operator_name=operator_name,
            result="success",
            client_ip=client_ip,
            user_agent=user_agent,
        )
        return ArticleDetailOut.model_validate(article)

    async def list_paginated(
        self,
        page: int,
        page_size: int,
        category_id: Optional[int] = None,
        user_id: Optional[int] = None,
        is_deleted: bool = False,
        order_by_field: Literal["id", "create_at"] = "create_at",
        keyword: Optional[str] = None,
    ) -> PageResponse[ArticleOut]:
        """is_deleted=True 走后台回收站（只返回已删除文章）。

        order_by_field：'create_at'（默认，按发布时间倒序）/ 'id'（按发布 id 倒序）。
        keyword：仅按标题模糊过滤（后台管理搜标题定位文章；多词 AND）。
        """
        items, total = await self.crud.list_paginated(
            page,
            page_size,
            category_id,
            user_id,
            is_deleted,
            order_by_field,
            keyword,
        )
        return page_response(
            [ArticleOut.model_validate(a) for a in items], total, page, page_size
        )

    async def list_infinite(
        self,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: Optional[str] = None,
        category_id: Optional[int] = None,
        user_id: Optional[int] = None,
        is_deleted: bool = False,
        order_by_field: Literal["id", "create_at"] = "create_at",
        keyword: Optional[str] = None,
    ) -> ArticleInfiniteOut:
        """无限滚动列表：按 (order_by_field desc, id desc) 取 limit 条，返回 has_more/next_cursor。

        limit 被限制在 [1, MAX_PAGE_SIZE] 之间，避免单次请求过大。
        cursor 非法（解码失败）→ ServiceError（→400），不落库查询。
        """
        if cursor:
            try:
                pos = decode_cursor(cursor)
            except Exception:
                raise ServiceError("无效的游标")
            # 本接口签发的游标必含 (create_at, id) 双键；缺任一键（如 {"i":1}）
            # 若放行到 dao 会拼出与 None 的比较表达式 → 500，故在此判无效游标。
            if pos.get("create_at") is None or pos.get("id") is None:
                raise ServiceError("无效的游标")
        if limit < 1:
            limit = DEFAULT_PAGE_SIZE
        if limit > MAX_PAGE_SIZE:
            limit = MAX_PAGE_SIZE
        items, has_more, next_cursor = await self.crud.list_infinite(
            limit,
            cursor=cursor,
            category_id=category_id,
            user_id=user_id,
            is_deleted=is_deleted,
            order_by_field=order_by_field,
            keyword=keyword,
        )
        return ArticleInfiniteOut(
            data=[ArticleOut.model_validate(a) for a in items],
            limit=limit,
            has_more=has_more,
            next_cursor=next_cursor,
        )

    async def search_paginated(
        self,
        *,
        keyword: str,
        scope: SearchScope,
        page: int,
        page_size: int,
        category_id: Optional[int] = None,
    ) -> PageResponse[ArticleSearchOut]:
        """公开搜索：多词 AND，结果按发布时间倒序；摘要为纯文本，高亮由前端完成。"""
        terms = split_terms(keyword)
        items, total = await self.crud.search_paginated(
            terms, scope.value, page, page_size, category_id
        )
        data: list[ArticleSearchOut] = []
        for article in items:
            item = ArticleSearchOut.model_validate(article)
            item.matched_terms = terms
            item.matched_fields = matched_fields(
                article.title, article.content, terms, scope.value
            )
            item.content_snippet = (
                build_snippet(article.content, terms)
                if scope in (SearchScope.all, SearchScope.content)
                else None
            )
            data.append(item)
        return page_response(data, total, page, page_size)

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
        operator_id: Optional[int] = None,
        operator_name: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[ArticleDetailOut]:
        """allow_admin_fields=False（普通用户）时剥离 user_id / create_at，其余字段照常更新"""
        fields = data.model_dump(exclude_unset=True)
        if not allow_admin_fields:
            fields.pop("user_id", None)
            fields.pop("create_at", None)
        article = await self.crud.update(slug, **fields)
        if article is None:
            await OperationService(self.session).log_operation(
                action="update_article",
                object_type="article",
                object_id=slug,
                object_name=None,
                operator_id=operator_id,
                operator_name=operator_name,
                result="failed",
                message="文章不存在",
                client_ip=client_ip,
                user_agent=user_agent,
            )
            return None
        article = await self.crud.get_by_slug(slug)
        await OperationService(self.session).log_operation(
            action="update_article",
            object_type="article",
            object_id=slug,
            object_name=article.title,
            operator_id=operator_id,
            operator_name=operator_name,
            result="success",
            client_ip=client_ip,
            user_agent=user_agent,
        )
        return ArticleDetailOut.model_validate(article)

    async def delete(
        self,
        slug: str,
        *,
        operator_id: Optional[int] = None,
        operator_name: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> bool:
        article = await self.crud.get_by_slug(slug)
        object_name = article.title if article else None
        result = await self.crud.soft_delete(slug)
        await OperationService(self.session).log_operation(
            action="delete_article",
            object_type="article",
            object_id=slug,
            object_name=object_name,
            operator_id=operator_id,
            operator_name=operator_name,
            client_ip=client_ip,
            user_agent=user_agent,
            result="success" if result else "failed",
            message=None if result else "文章不存在",
        )
        return result

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

    @staticmethod
    def _stats_window(current_user: User) -> tuple[ArticleStatsScope, str, datetime, Optional[int]]:
        """统计口径：超管=本月新增（全站，按发布时间）；普通用户=本人近 15 天发布"""
        now = datetime.now()
        if current_user.is_superuser:
            start_at = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return ArticleStatsScope.month, "本月新增文章", start_at, None
        return (
            ArticleStatsScope.half_month,
            "我的近半月发布",
            now - timedelta(days=15),
            current_user.id,
        )

    async def stats(self, current_user: User) -> ArticleStatsOut:
        """后台概览：按角色返回不同的发布量统计（超管本月新增 / 普通用户本人近半月）"""
        scope, label, start_at, user_id = self._stats_window(current_user)
        now = datetime.now()
        count = await self.crud.count_created_between(start_at, now, user_id)
        return ArticleStatsOut(
            scope=scope, label=label, count=count, start_at=start_at, end_at=now
        )
