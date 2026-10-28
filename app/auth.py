from datetime import datetime, timedelta, timezone
from typing import Callable, Optional
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel.ext.asyncio.session import AsyncSession
from app.database import get_session
from app.model import User
from app.settings import settings

ALGORITHM = "HS256"
bearer_scheme = HTTPBearer(auto_error=False)
AUTH_CHALLENGE = {"WWW-Authenticate": "Bearer"}


def unauthorized(detail: str) -> HTTPException:
    """401 错误工厂：统一带 WWW-Authenticate 响应头"""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers=AUTH_CHALLENGE
    )


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> Optional[User]:
    """可选鉴权：匿名（无凭据）返回 None；带凭据则必须有效——
    非法/过期 token 或用户已删除仍 401，不静默降级为匿名（避免权限收敛被绕过）"""
    if credentials is None:
        return None
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise unauthorized("无效或过期的令牌")
    user = await session.get(User, user_id)
    if user is None:
        raise unauthorized("用户不存在")
    return user


async def get_current_user(
    user: Optional[User] = Depends(get_optional_user),
) -> User:
    """必须鉴权：复用 get_optional_user，仅补上「未提供凭据」的 401"""
    if user is None:
        raise unauthorized("未提供认证凭据")
    return user


def require_superuser(detail: str = "仅超级管理员可执行此操作") -> Callable[..., User]:
    """依赖工厂：仅超管可用的接口；普通用户 → 403（各模块传入专属 detail 文案）"""

    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        if not current_user.is_superuser:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
        return current_user

    return dependency
