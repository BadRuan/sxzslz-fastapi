from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn import run
from app.database import init_db
from app.routers import user_router, category_router, article_router


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
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=False, # 允许跨域请求携带凭据（如 Cookies）
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有请求头
)

app.include_router(user_router, prefix='/user', tags=['用户模块'])
app.include_router(category_router, prefix='/category', tags=['分类模块'])
app.include_router(article_router, prefix='/article', tags=['文章模块'])


if __name__ == '__main__':
    run(app, host='0.0.0.0', port=8088)