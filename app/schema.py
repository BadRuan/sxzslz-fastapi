from typing import Dict, List, TypeVar, Generic
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

def pagination(cur_page: int, page_size: int, total_size: int) -> Dict:
    """计算分页元数据"""
    total_pages = ceil(total_size / page_size) if page_size > 0 else 0
    return {
        "cur_page": cur_page,
        "page_size": page_size,
        "total_size": total_size,
        "total_pages": total_pages,
    }
