"""操作日志数据访问层。

仅负责把一条 OperationLog 记录 flush 进当前会话，不自行 commit；
会话的提交/回滚由调用方（OperationService 的独立会话）负责。
"""

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import desc, func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.model import OperationLog

from app.types import DEFAULT_PAGE_SIZE


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

    async def list_paginated(
        self,
        *,
        action: Optional[str] = None,
        object_type: Optional[str] = None,
        operator_id: Optional[int] = None,
        result: Optional[str] = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> Tuple[List[OperationLog], int]:
        """分页查询操作日志（created_at desc, id desc），条件全部可选。"""
        conditions = []
        if action is not None:
            conditions.append(OperationLog.action == action)
        if object_type is not None:
            conditions.append(OperationLog.object_type == object_type)
        if operator_id is not None:
            conditions.append(OperationLog.operator_id == operator_id)
        if result is not None:
            conditions.append(OperationLog.result == result)

        base = select(OperationLog)
        if conditions:
            base = base.where(*conditions)

        count_stmt = select(func.count()).select_from(base.subquery())
        total: int = (await self.session.exec(count_stmt)).one()

        stmt = (
            base.order_by(desc(OperationLog.created_at), desc(OperationLog.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.exec(stmt)).all()
        return list(rows), total
