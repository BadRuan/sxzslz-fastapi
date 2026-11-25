import base64
import json
from datetime import datetime
from typing import Optional

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


# ---------- 无限滚动游标 ----------


def encode_cursor(create_at: Optional[datetime], id: int) -> str:
    """把（create_at, id）编码为 URL-safe Base64 游标字符串。

    id 是唯一的，配合 create_at 做双重排序键，保证翻页时无重复、无遗漏。
    首次请求不传 cursor（返回 None）。
    """
    payload: dict = {"i": id}
    if create_at is not None:
        payload["c"] = create_at.isoformat()
    return base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()


def decode_cursor(cursor: str) -> dict:
    """解码游标字符串，返回 {"create_at": datetime|None, "id": int}。"""
    payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    result: dict = {"id": int(payload["i"])}
    if "c" in payload:
        result["create_at"] = datetime.fromisoformat(payload["c"])
    return result


class ArticleInfiniteOut(BaseModel):
    """无限滚动分页响应：data 为本批文章，has_more 表示是否还有后续数据，
    next_cursor 为下一次请求应传入的 cursor（无更多数据时为 None）。"""

    data: list = Field(default_factory=list, description="本批文章列表")
    limit: int = Field(description="本次请求的条数上限")
    has_more: bool = Field(description="是否还有后续数据")
    next_cursor: str | None = Field(description="下一批数据的游标，None 表示已无更多数据")

