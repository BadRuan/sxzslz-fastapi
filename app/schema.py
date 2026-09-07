from typing import List, TypeVar, Generic, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from fastapi import Query

T = TypeVar("T")

class PaginationParams:
    def __init__(
        self,
        page: int = Query(1, ge=1, description="页码，从1开始"),
        size: int = Query(20, ge=1, le=100, description="每页条数，最大100")
    ) -> None:
        self.page = page
        self.size = size
        self.offset = (page - 1) * size

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

class ArticleCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    article_id: int
    category_id: int
    is_primary: int
    category_name: Optional[str] = ''


class UserCount(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    slug: str
    nickname: str


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
          
    slug: str
    cover_img_slug: str
    title: str
    status: int
    is_recommended: bool
    create_at: datetime
    view_count: int
    like_count: int
    category: Optional[CategoryTree] = None
    user: Optional[UserOut] = None
    
class ArticleDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    slug: str
    cover_img_slug: str
    title: str
    content: Optional[str]
    status: int
    is_recommended: bool
    create_at: datetime
    view_count: int
    like_count: int
    user: Optional[UserOut] = None
    primary_category: Optional[ArticleCategoryOut] =None
