import asyncio
from os import makedirs, remove
from os.path import exists
from typing import Iterable

from fastapi import UploadFile

DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1MB


class FileTooLargeError(ValueError):
    """上传字节数超过上限；由 service 层转为 ServiceError → 400"""

    def __init__(self, limit_bytes: int) -> None:
        self.limit_bytes = limit_bytes
        super().__init__(f"文件大小超过限制（最大 {limit_bytes} 字节）")


def ensure_dirs(dirs: Iterable[str]) -> None:
    for d in dirs:
        makedirs(d, exist_ok=True)


def write_bytes_sync(filepath: str, content: bytes) -> None:
    with open(filepath, "wb") as f:
        f.write(content)


async def write_bytes_async(filepath: str, content: bytes) -> None:
    """async 上下文里的落盘：阻塞文件写入放到线程池，不卡事件循环"""
    await asyncio.to_thread(write_bytes_sync, filepath, content)


async def write_upload_stream(
    filepath: str,
    file: UploadFile,
    max_bytes: int | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> int:
    """分块流式落盘上传文件（边收边写，避免整文件进内存）；返回总字节数。

    超过 max_bytes 时删除半成品并抛 FileTooLargeError。
    """
    total = 0
    try:
        with open(filepath, "wb") as f:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total += len(chunk)
                if max_bytes is not None and total > max_bytes:
                    raise FileTooLargeError(max_bytes)
                f.write(chunk)
    except FileTooLargeError:
        if exists(filepath):
            remove(filepath)
        raise
    return total

