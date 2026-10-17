from pydantic import BaseModel, Field


class PageResponse[T](BaseModel):
    data: list[T] = Field(default_factory=list, description="当前页数据列表")
    total: int = Field(description="总记录数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页条数")
    has_next: bool = Field(description="是否有下页")
