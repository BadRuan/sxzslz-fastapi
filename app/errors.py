import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger("sxzslz.error")


class ServiceError(ValueError):
    """业务校验错误（无效分类、字段为空、批量目标缺失等）。

    继承 ValueError：既有 pytest.raises(ValueError) / 调用方 except 兼容，
    又由全局 handler 统一转为 400 {"detail": "..."}，路由层无需逐个 try/except。
    """


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def handle_service_error(request: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        """未预期异常统一 JSON 500，前端任何接口都能拿到 {"detail": ...}；完整堆栈进日志"""
        logger.exception("未预期异常 %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "服务器内部错误"},
        )
