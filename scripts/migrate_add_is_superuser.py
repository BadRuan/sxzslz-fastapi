"""一次性迁移：给 user 表补 is_superuser 列，并把 ruanfumin 置为超级管理员。

幂等，可重复执行：
- ADD COLUMN IF NOT EXISTS：列已存在则跳过
- UPDATE username='ruanfumin' SET is_superuser=TRUE：重复执行结果一致

用法：uv run python scripts/migrate_add_is_superuser.py
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.settings import settings  # noqa: E402

SUPERUSER_USERNAME = "ruanfumin"


async def migrate() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as conn:
            print(f"目标库: {engine.url.render_as_string(hide_password=True)}")

            before = (
                await conn.execute(
                    text(
                        "SELECT is_nullable, column_default FROM information_schema.columns "
                        "WHERE table_name = 'user' AND column_name = 'is_superuser'"
                    )
                )
            ).first()
            count = (await conn.execute(text("SELECT count(*) FROM \"user\""))).scalar_one()
            print(f"[迁移前] user: 行数={count}, is_superuser 列={before or '不存在'}")

            await conn.execute(
                text(
                    "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS is_superuser BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            result = await conn.execute(
                text(
                    "UPDATE \"user\" SET is_superuser = TRUE WHERE username = :uname AND is_superuser = FALSE"
                ),
                {"uname": SUPERUSER_USERNAME},
            )
            print(f"[迁移] 已将 username={SUPERUSER_USERNAME} 置为超管，本次更新 {result.rowcount} 行")

            after = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM \"user\" WHERE is_superuser = TRUE"
                    )
                )
            ).scalar_one()
            print(f"[迁移后] 超管人数={after}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
