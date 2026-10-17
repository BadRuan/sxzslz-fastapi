import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.settings import settings

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
)


async def get_session():
    """请求级会话：成功结束自动 commit，异常 rollback。DAO 层只 flush，不自行 commit。"""
    async with AsyncSession(engine) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def _upgrade_to_head() -> None:
    cfg = Config(str(_PROJECT_ROOT / "alembic.ini"))
    command.upgrade(cfg, "head")


async def init_db() -> None:
    """启动时执行 Alembic 迁移到 head（替代原先 create_all + 幂等 SQL）。"""
    await asyncio.to_thread(_upgrade_to_head)
