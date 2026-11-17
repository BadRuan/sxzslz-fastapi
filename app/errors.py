"""全局业务错误与异常处理器（兼容层，重导出自 app.core.error）。

新代码请直接导入 `app.core.error`。
"""

from app.core.error import ServiceError, register_error_handlers  # noqa: F401

__all__ = ["ServiceError", "register_error_handlers"]
