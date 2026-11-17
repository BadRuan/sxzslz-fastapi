"""数据库会话与建表（兼容层，重导出自 app.core.database）。

保留此路径是为了兼容 AGENTS.md 约定与现有导入；新代码请直接
导入 `app.core.database`。

注意：`init_db` 在此层定义并绑定本模块的 `engine`，以便测试可通过
`monkeypatch.setattr(app.database, "engine", ...)` 注入测试引擎；
`engine` / `get_session` 仍从 `app.core.database` 重导出，二者在生产
环境中指向同一个异步引擎。
"""

from app.core.database import engine, get_session  # noqa: F401
from sqlmodel import SQLModel

__all__ = ["engine", "get_session", "init_db"]


async def init_db() -> None:
    """启动时建表（兼容层）：使用本模块 engine，便于测试替换。

    create_all 幂等，已存在的表会跳过，因此每次启动都
    可安全执行一次。
    """
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
