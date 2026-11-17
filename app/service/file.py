"""文件（图片 / 文档）上传服务的共用基类。

图片与文档的上传流程完全一致：

    MIME 白名单校验 → 生成 slug + 后缀 → 确保目录 → 分块流式落盘（1MB/块，带上限）
    → 空文件清理 → 类型特有后处理（图片：MD5 内容去重 + WebP 预览；文档：无）
    → 写入 DB 记录 → 返回记录。

`add_many` 在此统一实现：先整批校验类型，再逐个落盘；任一文件失败 →
抛 ServiceError（400），本批已落盘的文件立即清理，DB 记录随请求事务回滚，
不留半成品。

子类只需覆写 `ensure_type`、`post_upload`、`remove_file` 及构造时的
`slug_factory`/`max_bytes`/`size_limit_msg`/`dirs` 即可。
"""

import hashlib
from dataclasses import dataclass
from os import path, remove
from pathlib import Path
from typing import Callable, Generic, Literal, Optional, TypeVar

from fastapi import UploadFile
from PIL import UnidentifiedImageError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.dao.file import FileCrud
from app.errors import ServiceError
from app.settings import settings, upload_dir
from app.utils import (
    FileTooLargeError,
    StorageError,
    ensure_dirs,
    file_error,
    generate_webp_images,
    storage_error_from,
    write_upload_stream,
)

ModelT = TypeVar("ModelT")


@dataclass
class _UploadResult:
    action: Literal["proceed", "dedup_hit"]
    record: Optional[ModelT] = None
    md5: Optional[str] = None


def _md5_file(filepath: str) -> str:
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class BaseFileService(Generic[ModelT]):
    def __init__(
        self,
        crud: FileCrud[ModelT],
        *,
        slug_factory: Callable[[], str],
        max_bytes: int,
        size_limit_msg: str,
        dirs: tuple[str, ...],
    ) -> None:
        self.crud = crud
        self.slug_factory = slug_factory
        self.max_bytes = max_bytes
        self.size_limit_msg = size_limit_msg
        self.dirs = dirs

    # ---------- 子类覆写：差异点 ----------
    def ensure_type(self, content_type: str | None) -> None:
        """MIME 白名单校验；子类必须实现。"""
        raise NotImplementedError

    async def post_upload(self, slugname: str, raw_path: str) -> _UploadResult:
        """落盘后的类型特有处理。默认无额外处理（文档用此默认实现）。

        返回 action="dedup_hit" 时表示已命中重复内容、文件已清理，
        调用方应直接返回 result.record；否则返回 md5 用于写入 DB。
        """
        return _UploadResult(action="proceed", md5=None)

    def remove_file(self, slugname: str) -> None:
        """删除磁盘上的原始文件；图片子类会覆写以同时删除预览图。"""
        if path.isfile(raw_path := path.join(self.dirs[0], slugname)):
            remove(raw_path)

    # ---------- 共用模板：add ----------
    async def add(
        self, filename: str, mime_type: str, file: UploadFile, user_id: int
    ) -> Optional[ModelT]:
        self.ensure_type(mime_type)
        suffix = Path(filename).suffix
        slugname = self.slug_factory() + suffix
        raw_path = path.join(self.dirs[0], slugname)
        # 只在真正落盘时确保目录存在（exist_ok，避免每个请求都建目录）
        ensure_dirs(self.dirs)
        try:
            size = await write_upload_stream(raw_path, file, max_bytes=self.max_bytes)
        except FileTooLargeError:
            raise ServiceError(self.size_limit_msg)
        except StorageError as exc:
            raise ServiceError(str(exc)) from exc
        if size == 0:
            remove(raw_path)
            raise ServiceError("文件内容为空")

        result = await self.post_upload(slugname, raw_path)
        if result.action == "dedup_hit":
            return result.record
        await self.crud.add(
            raw_filename=filename,
            slug=slugname,
            mime_type=mime_type,
            size=size,
            user_id=user_id,
            md5=result.md5,
        )
        return await self.crud.get_by_slug(slugname)

    # ---------- 共用模板：add_many（整批原子） ----------
    async def add_many(self, files: list[UploadFile], user_id: int) -> list[ModelT]:
        """多文件同时上传：先整批校验类型，再逐个落盘。

        整批原子：任一文件失败 → 抛 ServiceError（400），本批已落盘的文件
        在异常路径立即清理，DB 记录随请求事务回滚，不留半成品。
        """
        if not files:
            raise ServiceError("请至少选择一个文件")
        if len(files) > settings.MAX_BATCH_FILES:
            raise ServiceError(f"单次最多上传 {settings.MAX_BATCH_FILES} 个文件")
        # 先整批校验类型，避免写入部分文件后才发现第 N 个文件类型非法
        for index, file in enumerate(files, start=1):
            try:
                self.ensure_type(file.content_type)
            except ServiceError as exc:
                raise ServiceError(file_error(index, file, exc)) from exc

        created: list[ModelT] = []
        try:
            for index, file in enumerate(files, start=1):
                try:
                    item = await self.add(
                        filename=file.filename or "default_name",
                        mime_type=file.content_type or "",
                        file=file,
                        user_id=user_id,
                    )
                except ServiceError as exc:
                    raise ServiceError(file_error(index, file, exc)) from exc
                if item is None:
                    raise ServiceError(file_error(index, file, "上传失败"))
                created.append(item)
        except Exception:
            # 清理本批已写入的文件与记录；DB 由 get_session 统一 rollback
            for item in created:
                await self.remove(item.slug)
            raise
        return created

    # ---------- 共用模板：其余 CRUD ----------
    async def find_by_slug(self, slugname: str) -> Optional[ModelT]:
        """只读查询，不自增 view（权限校验 / 改名前定位用）"""
        return await self.crud.get_by_slug(slugname)

    async def rename(self, slugname: str, raw_filename: str) -> Optional[ModelT]:
        """改展示名；记录不存在返回 None"""
        return await self.crud.update_raw_filename(slugname, raw_filename)

    async def remove(self, slugname: str) -> bool:
        """删除 DB 记录并清理磁盘文件；记录不存在返回 False"""
        result = await self.crud.remove_by_slug(slugname)
        if result:
            self.remove_file(slugname)
            return True
        return False

    async def get_by_slug(self, slugname: str) -> Optional[ModelT]:
        item: Optional[ModelT] = await self.crud.get_by_slug(slugname)
        if item is None:
            return None
        # 原子自增并用 RETURNING 的新计数就地更新，省掉一次 refresh 查询
        new_view = await self.crud.record_view(slugname)
        if new_view is not None:
            item.view = new_view
        return item
