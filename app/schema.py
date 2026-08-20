from typing import Dict, List, TypeVar, Generic, Optional
from datetime import datetime
from math import ceil
from pydantic import BaseModel, Field
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

def pagination(cur_page: int, page_size: int, total_size: int) -> Dict:
    """计算分页元数据"""
    total_pages = ceil(total_size / page_size) if page_size > 0 else 0
    return {
        "cur_page": cur_page,
        "page_size": page_size,
        "total_size": total_size,
        "total_pages": total_pages,
    }

class ArticleOut(BaseModel):
    slug: str
    cover_img: str
    title: str
    category_id: int
    user_id: int
    view_count: int
    is_public: bool
    is_recommended: bool
    create_at: datetime

    class Config:
        from_attributes = True

class ArticleDetailOut(BaseModel):
    slug: str
    cover_img: str
    title: str
    content: Optional[str]
    category_id: int
    user_id: int
    view_count: int
    is_public: bool
    is_recommended: bool
    create_at: datetime

    class Config:
        from_attributes = True

class CountOut(BaseModel):
    total_article: int
    month_article: int
    image_count: int
    attachment_count: int
    user_count: int
    article_view: int
    image_view: int
    download_count: int

class CategoryDetail(BaseModel):
    id: int
    name: str
    article_count: int
    view_count: int
    