"""Alembic 迁移可在干净 SQLite 上完整建表"""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from app import settings as settings_module

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_alembic_upgrade_creates_schema(tmp_path, monkeypatch):
    db_path = tmp_path / "mig.db"
    monkeypatch.setattr(
        settings_module.settings,
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{db_path}",
    )

    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(cfg, "head")

    async def _table_names():
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        async with engine.connect() as conn:
            names = await conn.run_sync(lambda c: inspect(c).get_table_names())
        await engine.dispose()
        return set(names)

    import asyncio

    names = asyncio.run(_table_names())
    assert {
        "user",
        "category",
        "article",
        "article_category",
        "image",
        "document",
        "alembic_version",
    } <= names
