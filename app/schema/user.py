from pydantic import BaseModel, ConfigDict, Field

from app.schema.category import CategoryTree


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    nickname: str
    is_superuser: bool = False


class UserCreate(BaseModel):
    """POST /users/：超管创建普通账户。密码缺省为 settings.DEFAULT_USER_PASSWORD（abc123）"""

    username: str = Field(min_length=1, max_length=64, description="登录名（唯一）")
    nickname: str = Field(min_length=1, max_length=64, description="展示名（唯一）")
    password: str | None = Field(
        default=None, min_length=6, max_length=128, description="密码，缺省 abc123"
    )


class PasswordResetOut(BaseModel):
    detail: str


class BaseInfoOut(BaseModel):
    """首页基础信息：分类树 + 用户列表。"""

    category: list[CategoryTree] = []
    user: list[UserOut] = []
