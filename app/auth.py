"""JWT Bearer 认证（兼容层，重导出自 app.core.auth）。

新代码请直接导入 `app.core.auth`。
"""

from app.core.auth import (  # noqa: F401
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

__all__ = [
    "ALGORITHM",
    "AUTH_CHALLENGE",
    "bearer_scheme",
    "create_access_token",
    "decode_access_token",
    "get_current_user",
    "get_optional_user",
    "require_superuser",
    "unauthorized",
]
