"""操作日志数据访问层。

仅负责把一条 OperationLog 记录 flush 进当前会话，不自行 commit；
会话的提交/回滚由调用方（OperationService 的独立会话）负责。
"""

from datetime import datetime
from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession
from app.model import OperationLog


class OperationLogCrud:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
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
        created_at: Optional[datetime] = None,
    ) -> OperationLog:
        log = OperationLog(
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
            created_at=created_at or datetime.now(),
        )
        self.session.add(log)
        await self.session.flush()
        return log
