"""一次性迁移：给 image 表补 md5 列，并为已有图片文件计算 MD5 回填。

幂等，可重复执行：
- ADD COLUMN IF NOT EXISTS
- 只回填 md5 IS NULL 的记录
- 文件缺失时跳过并打印警告

用法：uv run python scripts/migrate_add_image_md5.py
"""

import asyncio
import hashlib
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.settings import settings, upload_dir  # noqa: E402

async def _md5_file(filepath: Path) -> str | None:
    if not filepath.is_file():
        return None
    h = hashlib.md5()
    with filepath.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

async def migrate() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as conn:
            print(f"目标库: {engine.url.render_as_string(hide_password=True)}")
            await conn.execute(text("ALTER TABLE image ADD COLUMN IF NOT EXISTS md5 VARCHAR(32)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_image_md5 ON image (md5)"))

            rows = (await conn.execute(text("SELECT id, slug FROM image WHERE md5 IS NULL"))).all()
            print(f"待回填记录数: {len(rows)}")
            updated = 0
            skipped = 0
            for rid, slug in rows:
                filepath = Path(upload_dir.image_raw) / slug
                md5 = await _md5_file(filepath)
                if md5 is None:
                    print(f"  [跳过] id={rid} slug={slug} 文件不存在: {filepath}")
                    skipped += 1
                    continue
                await conn.execute(
                    text("UPDATE image SET md5 = :md5 WHERE id = :id"), {"md5": md5, "id": rid}
                )
                updated += 1
            print(f"完成：更新 {updated} 条，跳过 {skipped} 条")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())
