import os
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth import get_current_user
from app.database import get_session
from app.model import User
from app.schema import BaseInfoOut, StorageOut
from app.service import CategoryService, UserService
from app.settings import base_dir

router = APIRouter()


@router.get("/base/", response_model=BaseInfoOut)
async def get_base_info(session: AsyncSession = Depends(get_session)):
    categories = await CategoryService(session).get_tree()
    users = await UserService(session).get_all()
    return BaseInfoOut(category=categories, user=users)


def _existing_dir(path: Path) -> Path:
    """向上回溯到最近的已存在目录：上传目录首次部署时可能还未创建"""
    current = path
    while not current.exists() and current != current.parent:
        current = current.parent
    return current


def _dir_size(root: Path) -> int | None:
    """递归统计目录占用（字节）；无权限或目录缺失时返回 None"""
    if not root.is_dir():
        return 0
    total = 0
    try:
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in filenames:
                file_path = Path(dirpath, name)
                try:
                    total += file_path.stat().st_size
                except OSError:  # 单个文件被占用/无权限不影响整体统计
                    continue
    except OSError:
        return None
    return total


@router.get("/base/storage", response_model=StorageOut)
async def get_storage(_: User = Depends(get_current_user)):
    """站点容量（需登录）：上传目录所在磁盘的总量/已用/剩余，并附带上传目录占用"""
    upload_root = Path(base_dir)
    try:
        usage = shutil.disk_usage(_existing_dir(upload_root))
    except (OSError, ValueError) as exc:  # 磁盘不可读：明确报错，不返回假数据
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="无法读取磁盘容量信息",
        ) from exc
    percent = round(usage.used / usage.total * 100, 1) if usage.total else 0.0
    return StorageOut(
        total=usage.total,
        used=usage.used,
        free=usage.free,
        usage_percent=percent,
        uploads_bytes=_dir_size(upload_root),
    )
