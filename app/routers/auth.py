from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth import create_access_token, get_current_user
from app.database import get_session
from app.model import User
from app.schema import (
    LoginRequest,
    PasswordChangeOut,
    PasswordChangeRequest,
    TokenOut,
    UserOut,
)
from app.service import UserService

router = APIRouter()


@router.post("/login", response_model=TokenOut)
async def login(data: LoginRequest, session: AsyncSession = Depends(get_session)):
    user = await UserService(session).get_by_username(data.username)
    if user is None or not user.check_password(data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenOut(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user


@router.put("/password", response_model=PasswordChangeOut)
async def change_password(
    data: PasswordChangeRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """修改当前登录用户密码：校验旧密码（错误 → 400），新密码至少 6 位（否则 422）"""
    await UserService(session).change_password(
        current_user, data.old_password, data.new_password
    )
    return PasswordChangeOut(detail="密码修改成功")
