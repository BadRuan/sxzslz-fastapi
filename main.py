import logging
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from uvicorn import run

from app.database import init_db
from app.errors import register_error_handlers
from app.routers import (
    article_router,
    auth_router,
    baseinfo_router,
    category_router,
    document_router,
    image_router,
)
from app.settings import cors_origins

logger = logging.getLogger("sxzslz.access")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化数据库"""
    await init_db()
    yield


app = FastAPI(
    title="sxzslz-fastapi",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),  # 来自 settings.CORS_ORIGINS，不再全开
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 业务校验错误（ServiceError）→ 400 {"detail": ...}，路由层无需各自 try/except
register_error_handlers(app)


@app.middleware("http")
async def log_request_duration(request: Request, call_next):
    """访问日志：记录每个请求的状态码与耗时，便于定位慢接口"""
    started_at = perf_counter()
    response = await call_next(request)
    duration_ms = (perf_counter() - started_at) * 1000
    logger.info(
        "%s %s -> %s (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


for router, prefix, tags in [
    (auth_router, "/auth", ["认证模块"]),
    (baseinfo_router, "", ["基础信息模块"]),
    (category_router, "/categories", ["分类模块"]),
    (article_router, "/articles", ["文章模块"]),
    (image_router, "/image", ["图片模块"]),
    (document_router, "/document", ["文件模块"]),
]:
    app.include_router(router, prefix=prefix, tags=tags)


if __name__ == '__main__':
    run(app, host='0.0.0.0', port=8088)
