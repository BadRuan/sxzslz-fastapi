"""全局通用常量与类型别名。

将散落在 settings/service/dao/routers 中的重复文案、允许值集合、
业务规则阈值等在此集中定义，供各层复用，避免同一份字符串在多处
重复维护而导致不一致。
"""

from typing import Final, FrozenSet

# 文章列表允许的排序字段：仅这两个值，避免字符串拼写散落在各处
ARTICLE_ORDER_FIELDS: Final[FrozenSet[str]] = frozenset({"id", "create_at"})

# 文章可空字段：显式传 null 表示清空；非空字段传 null 应返回 400
ARTICLE_NULLABLE_FIELDS: Final[FrozenSet[str]] = frozenset({"content", "cover_img_slug"})

# 分类写操作 / 用户账户管理专属 403 文案（各模块引用，统一文案）
CATEGORY_MANAGE_FORBIDDEN: Final[str] = "仅超级管理员可管理文章分类"
ACCOUNT_MANAGE_FORBIDDEN: Final[str] = "仅超级管理员可管理用户账户"

# 文件（图片/文档）管理专属 403 文案
FILE_FORBIDDEN: Final[str] = "无权限操作该文件"

# 文章修改权限专属 403 文案
ARTICLE_FORBIDDEN: Final[str] = "无权修改他人文章"
ARTICLE_DELETE_FORBIDDEN: Final[str] = "无权删除他人文章"
ARTICLE_RESTORE_FORBIDDEN: Final[str] = "无权恢复他人文章"

# 默认分页参数
DEFAULT_PAGE: Final[int] = 1
DEFAULT_PAGE_SIZE: Final[int] = 20
MAX_PAGE_SIZE: Final[int] = 100

# 图片/文档列表默认页大小
FILE_DEFAULT_PAGE_SIZE: Final[int] = 30
