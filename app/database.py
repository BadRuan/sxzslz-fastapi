from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from app.settings import settings

# 导入全部模型以注册到 SQLModel.metadata：缺了这行，create_all 会一张表也建不出来
from app import model  # noqa: F401

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
)


async def get_session():
    """请求级会话：成功结束自动 commit，异常 rollback。DAO 层只 flush，不要自行 commit。
    （退出 with 块时由上下文管理器负责 close，无需手动 finally。）"""
    async with AsyncSession(engine) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """启动时建表。create_all 幂等，已存在的表会跳过，因此每次启动都可安全执行一次。"""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
