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

        写入失败不抛出，仅记 Python 日志，避免影响主业务响应。
        """
        try:
            crud = OperationLogCrud(self.session)
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
            await self.session.flush()
        except Exception:  # 日志写入失败绝不影响主业务
            logger.exception(
                "操作日志写入失败: action=%s object_type=%s object_id=%s",
                action,
                object_type,
                object_id,
            )
