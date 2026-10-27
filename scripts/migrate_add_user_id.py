"""一次性迁移：给 image / document 表补 user_id 列（必填、无默认），存量数据置 1。

幂等，可重复执行：
- ADD COLUMN IF NOT EXISTS：列已存在则跳过
- UPDATE ... WHERE user_id IS NULL：只回填空值
- SET NOT NULL：已满足则为空操作

用法：uv run python scripts/migrate_add_user_id.py
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# 以文件方式运行（uv run python scripts/xxx.py）时把项目根加入搜索路径
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.settings import settings  # noqa: E402

TABLES = ("image", "document")
LEGACY_USER_ID = 1


async def migrate() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as conn:
            print(f"目标库: {engine.url.render_as_string(hide_password=True)}")

            for table in TABLES:
                before = (
                    await conn.execute(
                        text(
                            "SELECT is_nullable, column_default FROM information_schema.columns "
                            "WHERE table_name = :t AND column_name = 'user_id'"
                        ),
                        {"t": table},
                    )
                ).first()
                count = (
                    await conn.execute(text(f"SELECT count(*) FROM {table}"))  # noqa: S608
                ).scalar_one()
                print(f"[迁移前] {table}: 行数={count}, user_id 列={before or '不存在'}")

            # 单事务包住全部变更：任一失败整体回滚
            for table in TABLES:
                await conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS user_id INTEGER")  # noqa: S608
                )
                await conn.execute(
                    text(
                        f"UPDATE {table} SET user_id = :uid WHERE user_id IS NULL"  # noqa: S608
                    ),
                    {"uid": LEGACY_USER_ID},
                )
                await conn.execute(
                    text(f"ALTER TABLE {table} ALTER COLUMN user_id SET NOT NULL")  # noqa: S608
                )
                await conn.execute(
                    text(f"ALTER TABLE {table} ALTER COLUMN user_id DROP DEFAULT")  # noqa: S608
                )

            for table in TABLES:
                col = (
                    await conn.execute(
                        text(
                            "SELECT is_nullable, column_default FROM information_schema.columns "
                            "WHERE table_name = :t AND column_name = 'user_id'"
                        ),
                        {"t": table},
                    )
                ).first()
                dist = (
                    await conn.execute(
                        text(f"SELECT user_id, count(*) FROM {table} GROUP BY user_id ORDER BY user_id"),  # noqa: S608
                    )
                ).all()
                print(f"[迁移后] {table}: user_id 列={col}, user_id 分布={[(r[0], r[1]) for r in dist]}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
