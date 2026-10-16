from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from .settings import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_pre_ping=True
)

async def get_session():
    async with AsyncSession(engine) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        # create_all 不会为已存在的表新增列，这里幂等地补齐软删除字段
        await conn.execute(text("ALTER TABLE article ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE"))
        await conn.execute(text("ALTER TABLE category ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE"))
        # name/slug 唯一性从全表唯一改为「仅活跃行」部分索引，软删后允许复用
        await conn.execute(text("ALTER TABLE category DROP CONSTRAINT IF EXISTS category_name_key"))
        await conn.execute(text("ALTER TABLE category DROP CONSTRAINT IF EXISTS category_slug_key"))
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_category_name ON category (name) WHERE NOT is_deleted"))
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_category_slug ON category (slug) WHERE NOT is_deleted"))
    