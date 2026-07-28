from pydantic import BaseModel
from sqlmodel import Field
from typing import List, TypeVar, Generic

class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, description="页码 从1开始")
    page_size: int = Field(default=10, ge=1, le=100, description="每页条数 最大100")

T = TypeVar("T")

class PageResponse(BaseModel, Generic[T]):
    total: int = Field(description="总记录数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页条数")
    items: List[T] = Field(description="当前页数据列表")