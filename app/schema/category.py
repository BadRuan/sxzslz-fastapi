from pydantic import BaseModel, ConfigDict


class CategoryTree(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort: int
    children: list["CategoryTree"] = []


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    parent_id: int
    sort: int


class CategoryCreate(BaseModel):
    name: str
    parent_id: int = 0
    sort: int = 0


class CategoryUpdate(BaseModel):
    """部分更新。一级分类不可调父级；二级分类仅可改挂到另一个一级分类下。"""

    name: str | None = None
    parent_id: int | None = None
    sort: int | None = None
