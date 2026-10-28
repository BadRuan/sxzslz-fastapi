import asyncio
import errno
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


class StorageError(ValueError):
    """落盘失败（磁盘满 / 无权限 / 其他 I/O 错误）；由 service 层转为 ServiceError → 400"""


def storage_error_from(exc: OSError) -> StorageError:
    """把底层 OSError 归类为用户可读的 StorageError（磁盘满 / 权限 / 其他）"""
    if exc.errno == errno.ENOSPC:
        return StorageError("服务器磁盘空间已满，请联系管理员清理后重试")
    if exc.errno in (errno.EACCES, errno.EPERM):
        return StorageError("服务器存储目录无写入权限，请联系管理员")
    return StorageError("文件保存到服务器失败，请稍后重试")


def _remove_quietly(filepath: str) -> None:
    """清理半成品文件；失败（已不存在等）不抛出，避免掩盖原始错误"""
    try:
        if exists(filepath):
            remove(filepath)
    except OSError:
        pass


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

    超过 max_bytes 删除半成品并抛 FileTooLargeError；
    磁盘满 / 无权限 / 写入失败删除半成品并抛 StorageError。
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
        _remove_quietly(filepath)
        raise
    except OSError as exc:
        _remove_quietly(filepath)
        raise storage_error_from(exc) from exc
    return total

