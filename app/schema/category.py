from pydantic import BaseModel, ConfigDict


class CategoryTree(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    path: str
    level: int
    sort: int
    children: list["CategoryTree"] = []


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    parent_id: int
    path: str
    level: int
    sort: int


class CategoryCreate(BaseModel):
    name: str
    slug: str
    parent_id: int = 0
    sort: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    parent_id: int | None = None
    sort: int | None = None
