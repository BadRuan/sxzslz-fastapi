from pydantic import BaseModel, ConfigDict

from app.schema.category import CategoryTree


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    nickname: str
    is_superuser: bool = False


class BaseInfoOut(BaseModel):
    """首页基础信息：分类树 + 用户列表。"""

    category: list[CategoryTree] = []
    user: list[UserOut] = []
