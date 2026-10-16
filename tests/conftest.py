import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.model import User, Article, Category, ArticleCategory, Image, Document  # noqa: F401


@pytest.fixture
async def engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine):
    async with AsyncSession(engine) as session:
        yield session


@pytest.fixture
async def default_user(session):
    user = User(username="admin", nickname="管理员", password="test")
    session.add(user)
    await session.flush()
    return user
