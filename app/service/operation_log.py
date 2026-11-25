"""操作日志服务层。

沿用项目“DAO 层只 flush、会话由请求方统一 commit/rollback”的约定：
- `log_operation` 向注入的请求会话写入日志并 flush，随主请求一起 commit。
- 若主业务因 `ServiceError` 抛出而回滚，随之回滚的还包括当前请求的日志；
  日志写入本身若失败，捕获并写 Python 日志，不抛出，保证不影响主响应。

若后续需要“主事务回滚时日志仍保留”，可在此改为使用独立会话并自行 commit；
需注意测试环境为内存 SQLite，独立会话须指向同一测试引擎。
"""

import logging
from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.dao import OperationLogCrud
from app.schema import OperationLogOut, PageResponse, page_response
from app.types import DEFAULT_PAGE_SIZE

logger = logging.getLogger("sxzslz.operation")


class OperationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log_operation(
        self,
        *,
        action: str,
        object_type: str,
        object_id: str,
        object_name: Optional[str] = None,
        operator_id: Optional[int] = None,
        operator_name: Optional[str] = None,
        result: str = "success",
        message: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """向请求会话写入一条操作日志（仅 flush，commit 由请求会话负责）。

        写入不抛出，失败仅记 Python 日志，避免影响主业务响应。
        整个写入包在 SAVEPOINT（begin_nested）里：日志写失败只回滚到保存点，
        不污染主事务——否则半成品日志行会随主请求提交，且 DB 层错误
        （PostgreSQL 事务 aborted）会连带把主业务一起打死。
        """
        try:
            crud = OperationLogCrud(self.session)
            async with self.session.begin_nested():
                await crud.add(
                    action=action,
                    object_type=object_type,
                    object_id=object_id,
                    object_name=object_name,
                    operator_id=operator_id,
                    operator_name=operator_name,
                    result=result,
                    message=message,
                    client_ip=client_ip,
                    user_agent=user_agent,
                )
        except Exception:  # 日志写入失败绝不影响主业务
            logger.exception(
                "操作日志写入失败: action=%s object_type=%s object_id=%s",
                action,
                object_type,
                object_id,
            )

    async def list_paginated(
        self,
        *,
        action: Optional[str] = None,
        object_type: Optional[str] = None,
        operator_id: Optional[int] = None,
        result: Optional[str] = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> PageResponse[OperationLogOut]:
        """分页查询操作日志（仅超管路由调用）。"""
        rows, total = await OperationLogCrud(self.session).list_paginated(
            action=action,
            object_type=object_type,
            operator_id=operator_id,
            result=result,
            page=page,
            page_size=page_size,
        )
        return page_response(
            [OperationLogOut.model_validate(row) for row in rows],
            total,
            page,
            page_size,
        )
