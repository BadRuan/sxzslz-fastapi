from fastapi import Depends, HTTPException, status


def get_current_user_id() -> str:
    """获取当前登录用户 ID（占位，待接入认证中间件后实现）"""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未登录，请先认证",
    )


def login_required():
    """登录验证依赖（占位，待接入 JWT/Session 认证后实现）"""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未登录，请先认证",
    )
