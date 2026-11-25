"""一次性迁移：确认 operation_log.created_at 是 timestamp（含时分秒）列，必要时升级。

背景：操作日志时间字段需含时分秒。模型自建立以来一直是 datetime（TIMESTAMP），
本脚本是幂等兜底——仅当部署库该列被建成 date（只存日期、丢了时分秒）时，
升级为 timestamp(6)；已是 timestamp 则纯打印不做任何变更。

注意：date 列升级后旧数据时分秒为 00:00:00（原本就没有，无法找回）。

用法：uv run python scripts/migrate_logs_created_at_timestamp.py
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# 以文件方式运行（uv run python scripts/xxx.py）时把项目根加入搜索路径
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.settings import settings  # noqa: E402

TABLE = "operation_log"
COLUMN = "created_at"


async def migrate() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as conn:
            print(f"目标库: {engine.url.render_as_string(hide_password=True)}")

            before = (
                await conn.execute(
                    text(
                        "SELECT data_type FROM information_schema.columns "
                        "WHERE table_name = :t AND column_name = :c"
                    ),
                    {"t": TABLE, "c": COLUMN},
                )
            ).first()
            count = (
                await conn.execute(text(f"SELECT count(*) FROM {TABLE}"))  # noqa: S608
            ).scalar_one()
            print(f"[迁移前] {TABLE}: 行数={count}, {COLUMN} 列类型={before or '不存在'}")

            if before is not None and before[0] == "date":
                # date → timestamp(6)：旧值保留日期部分，时分秒为 00:00:00
                await conn.execute(
                    text(
                        f"ALTER TABLE {TABLE} ALTER COLUMN {COLUMN} "  # noqa: S608
                        f"TYPE timestamp(6) USING {COLUMN}::timestamp(6)"
                    )
                )

            after = (
                await conn.execute(
                    text(
                        "SELECT data_type FROM information_schema.columns "
                        "WHERE table_name = :t AND column_name = :c"
                    ),
                    {"t": TABLE, "c": COLUMN},
                )
            ).first()
            print(f"[迁移后] {TABLE}: {COLUMN} 列类型={after}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
