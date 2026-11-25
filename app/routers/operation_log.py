"""操作日志查询路由（GET /logs/，仅超管）。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth import require_superuser
from app.database import get_session
from app.model import User
from app.schema import OperationLogOut, PageResponse
from app.service.operation_log import OperationService
from app.types import (
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    LOG_QUERY_FORBIDDEN,
    MAX_PAGE_SIZE,
)

router = APIRouter()


@router.get("/", response_model=PageResponse[OperationLogOut])
async def list_logs(
    page: int = Query(default=DEFAULT_PAGE, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(
        default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="每页条数"
    ),
    action: Optional[str] = Query(default=None, description="按动作过滤（如 create_article）"),
    object_type: Optional[str] = Query(default=None, description="按对象类型过滤（article/document/...）"),
    operator_id: Optional[int] = Query(default=None, ge=1, description="按操作人用户 ID 过滤"),
    result: Optional[str] = Query(default=None, description="按结果过滤（success/failed）"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_superuser(LOG_QUERY_FORBIDDEN)),
):
    """分页查询操作日志（created_at desc, id desc），仅超级管理员。"""
    return await OperationService(session).list_paginated(
        action=action,
        object_type=object_type,
        operator_id=operator_id,
        result=result,
        page=page,
        page_size=page_size,
    )
