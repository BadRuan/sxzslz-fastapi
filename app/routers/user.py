from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth import get_current_user, require_superuser
from app.database import get_session
from app.model import User
from app.routers._common import client_info
from app.schema import PasswordResetOut, UserCreate, UserOut
from app.service import UserService
from app.types import ACCOUNT_MANAGE_FORBIDDEN

router = APIRouter()


@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_account(
    data: UserCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_superuser(ACCOUNT_MANAGE_FORBIDDEN)),
):
    """创建普通账户（仅超管）；密码缺省为 settings.DEFAULT_USER_PASSWORD（abc123）"""
    client_ip, user_agent = client_info(request)
    return await UserService(session).create(
        data,
        operator_id=current_user.id,
        operator_name=current_user.nickname,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@router.post("/{user_id}/reset-password", response_model=PasswordResetOut)
async def reset_account_password(
    user_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_superuser(ACCOUNT_MANAGE_FORBIDDEN)),
):
    """把普通账户密码重置为默认密码（仅超管）；超级管理员账户受保护"""
    client_ip, user_agent = client_info(request)
    service = UserService(session)
    target = await service.get_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if target.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="不能重置超级管理员密码"
        )
    return await service.reset_password(
        target,
        operator_id=current_user.id,
        operator_name=current_user.nickname,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    user_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_superuser(ACCOUNT_MANAGE_FORBIDDEN)),
):
    """删除普通账户（仅超管）：其文章与上传文件保留，作者关联变为空"""
    client_ip, user_agent = client_info(request)
    service = UserService(session)
    target = await service.get_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if target.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="不能删除超级管理员账户"
        )
    await service.delete(
        target,
        operator_id=current_user.id,
        operator_name=current_user.nickname,
        client_ip=client_ip,
        user_agent=user_agent,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
