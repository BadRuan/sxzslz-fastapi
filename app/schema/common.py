from pydantic import BaseModel, Field


class PageResponse[T](BaseModel):
    data: list[T] = Field(default_factory=list, description="当前页数据列表")
    total: int = Field(description="总记录数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页条数")
    has_next: bool = Field(description="是否有下页")


def page_response[T](data: list[T], total: int, page: int, page_size: int) -> PageResponse[T]:
    """统一分页组装（has_next 语义固定为 page * page_size < total），供各 service 复用"""
    return PageResponse(
        data=data,
        total=total,
        page=page,
        page_size=page_size,
        has_next=page * page_size < total,
    )
