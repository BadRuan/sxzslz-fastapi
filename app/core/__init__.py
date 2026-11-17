"""应用核心层：数据库会话、全局错误处理、JWT 认证。

从 app.database / app.errors / app.auth 搬迁而来，供 routers/service/DAO
统一导入，降低跨目录导入层数并避免循环引用。
"""

from app.core.auth import (
    ALGORITHM,
    AUTH_CHALLENGE,
    bearer_scheme,
    create_access_token,
    decode_access_token,
    get_current_user,
    get_optional_user,
    require_superuser,
    unauthorized,
)
from app.core.database import engine, get_session, init_db
from app.core.error import ServiceError, register_error_handlers

__all__ = [
    "ALGORITHM",
    "AUTH_CHALLENGE",
    "bearer_scheme",
    "create_access_token",
    "decode_access_token",
    "engine",
    "get_current_user",
    "get_optional_user",
    "get_session",
    "init_db",
    "register_error_handlers",
    "require_superuser",
    "ServiceError",
    "unauthorized",
]
