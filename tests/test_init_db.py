"""init_db 启动建表：每次项目启动自动执行一次，幂等建出全部表"""
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

import app.database as database
import main


async def test_startup_runs_init_db_once(monkeypatch):
    """需求：每次启动项目后，自动执行一次 init_db 建表"""
    calls = []

    async def fake_init_db():
        calls.append(1)

    monkeypatch.setattr(main, "init_db", fake_init_db)

    async with main.lifespan(main.app):
        pass

    assert calls == [1]


async def test_init_db_creates_all_tables(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(database, "engine", engine)

    await database.init_db()

    async with engine.connect() as conn:
        names = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
    await engine.dispose()

    assert {
        "user",
        "category",
        "article",
        "article_category",
        "image",
        "document",
    } <= names


async def test_init_db_is_idempotent(monkeypatch):
    """每次启动都执行一次：重复调用不得报错，已存在的表跳过"""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(database, "engine", engine)

    await database.init_db()
    await database.init_db()

    async with engine.connect() as conn:
        names = await conn.run_sync(lambda c: sorted(inspect(c).get_table_names()))
    await engine.dispose()

    assert {
        "user",
        "category",
        "article",
        "article_category",
        "image",
        "document",
    } <= set(names)


def test_no_database_foreign_keys():
    """需求守护：表间关联禁止使用数据库级外键，仅业务层关联"""
    from sqlmodel import SQLModel

    for table in SQLModel.metadata.tables.values():
        fks = list(table.foreign_keys)
        assert fks == [], f"表 {table.name} 存在数据库外键: {fks}"
