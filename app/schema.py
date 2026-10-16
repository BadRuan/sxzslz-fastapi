from typing import List, TypeVar, Generic, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

T = TypeVar("T")

class PageResponse(BaseModel, Generic[T]):
    data: List[T] = Field(default_factory=list, description="当前页数据列表")
    total: int = Field(description="总记录数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页条数")
    has_next: bool = Field(description="是否有下页")

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    slug: str
    nickname: str

class CategoryTree(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: str
    slug: str
    path: str
    level: int
    sort: int
    children: List["CategoryTree"] = []

class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    parent_id: int
    path: str
    level: int
    sort: int

class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
          
    id: int
    slug: str
    cover_img_slug: Optional[str] = None
    title: str
    is_hidden: bool
    is_recommended: bool
    create_at: datetime
    view_count: int
    like_count: int
    categories: List[CategoryTree] = []
    user: Optional[UserOut] = None


class ArticleDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    cover_img_slug: Optional[str] = None
    title: str
    content: Optional[str] = None
    is_hidden: bool
    is_recommended: bool
    create_at: datetime
    view_count: int
    like_count: int
    categories: List[CategoryTree] = []
    user: Optional[UserOut] = None


class CategoryCreate(BaseModel):
    name: str
    slug: str
    parent_id: int = 0
    sort: int = 0


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    parent_id: Optional[int] = None
    sort: Optional[int] = None


class ArticleCreate(BaseModel):
    title: str
    content: Optional[str] = None
    cover_img_slug: Optional[str] = None
    is_hidden: bool = False
    is_recommended: bool = False
    category_ids: List[int] = []


class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    cover_img_slug: Optional[str] = None
    is_hidden: Optional[bool] = None
    is_recommended: Optional[bool] = None
    category_ids: Optional[List[int]] = None
