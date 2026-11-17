"""数据库会话与建表（异步，SQLModel + SQLAlchemy）。

`engine` 按 settings.DATABASE_URL 创建；`get_session` 是请求级依赖：
请求成功结束时自动 commit，异常 rollback，DAO 层只 flush，不要自行 commit。
`init_db` 在应用启动时调用一次，幂等建出全部表。
"""

from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app import model  # noqa: F401  —— 导入全部模型，注册到 SQLModel.metadata
from app.settings import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
)


async def get_session():
    """请求级会话：成功结束自动 commit，异常 rollback。DAO 层只 flush，
    不要自行 commit。（退出 with 块时由上下文管理器负责 close。）"""
    async with AsyncSession(engine) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """启动时建表。create_all 幂等，已存在的表会跳过，因此每次启动都
    可安全执行一次。"""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
