from pydantic import BaseModel, Field


class StorageOut(BaseModel):
    """站点所在磁盘的容量概览（字节）：

    `total` 磁盘总容量、`used` 已用、`free` 剩余可用；`usage_percent` 为已用百分比。
    `uploads_bytes` 为本站上传目录累计占用（统计失败时为 None）。
    """

    total: int = Field(ge=0, description="磁盘总容量（字节）")
    used: int = Field(ge=0, description="磁盘已用（字节）")
    free: int = Field(ge=0, description="磁盘剩余可用（字节）")
    usage_percent: float = Field(ge=0, le=100, description="磁盘已用百分比（0-100）")
    uploads_bytes: int | None = Field(default=None, description="上传目录累计占用（字节）")
