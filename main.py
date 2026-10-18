from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn import run
from app.database import init_db
from app.settings import cors_origins
from app.routers import baseinfo_router, category_router, article_router, auth_router, image_router, document_router


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

app.include_router(auth_router, prefix='/auth', tags=['认证模块'])
app.include_router(baseinfo_router, tags=['基础信息模块'])
app.include_router(category_router, prefix='/categories', tags=['分类模块'])
app.include_router(article_router, prefix='/articles', tags=['文章模块'])
app.include_router(image_router, prefix='/image', tags=['图片模块'])
app.include_router(document_router, prefix='/document', tags=['文件模块'])


if __name__ == '__main__':
    run(app, host='0.0.0.0', port=8088)