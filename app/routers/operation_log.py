"""操作日志查询路由（GET /logs/，需登录）。

可见范围与 GET /articles/ 同约定：超管查全量（可按 operator_id 过滤）；
普通用户固定只看本人日志（operator_id 参数被忽略）。
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth import get_current_user
from app.database import get_session
from app.model import User
from app.schema import OperationLogOut, PageResponse
from app.service.operation_log import OperationService
from app.types import (
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
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
    operator_id: Optional[int] = Query(
        default=None, ge=1, description="按操作人用户 ID 过滤（仅超管生效；普通用户固定只看本人）"
    ),
    result: Optional[str] = Query(default=None, description="按结果过滤（success/failed）"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """分页查询操作日志（created_at desc, id desc）。

    超管查全量（可按 operator_id 过滤）；普通用户固定只看本人日志
    （operator_id 参数被忽略，同 GET /articles/ 的 user_id 约定）。
    """
    if not current_user.is_superuser:
        operator_id = current_user.id
    return await OperationService(session).list_paginated(
        action=action,
        object_type=object_type,
        operator_id=operator_id,
        result=result,
        page=page,
        page_size=page_size,
    )
