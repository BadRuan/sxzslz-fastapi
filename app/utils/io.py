import asyncio
from os import makedirs
from typing import Iterable


def ensure_dirs(dirs: Iterable[str]) -> None:
    for d in dirs:
        makedirs(d, exist_ok=True)


def write_bytes_sync(filepath: str, content: bytes) -> None:
    with open(filepath, "wb") as f:
        f.write(content)


async def write_bytes_async(filepath: str, content: bytes) -> None:
    """async 上下文里的落盘：阻塞文件写入放到线程池，不卡事件循环"""
    await asyncio.to_thread(write_bytes_sync, filepath, content)
