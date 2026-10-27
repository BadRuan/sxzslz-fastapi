import asyncio
from os import path
from typing import Tuple

from PIL import Image

from app.settings import upload_dir


def _has_transparency(img: Image.Image) -> bool:
    """是否带透明信息：RGBA/LA 直接可判；调色板图看 transparency（PNG tRNS / GIF 透明索引）。"""
    if img.mode in ("RGBA", "LA", "PA"):
        return True
    return "transparency" in img.info


def _generate_webp_sync(slug_name: str, preview_size: Tuple[int, int]) -> str:
    slug, _ = path.splitext(slug_name)
    path_raw = path.join(upload_dir.image_raw, slug_name)
    path_preview = path.join(upload_dir.image_preview, slug + ".webp")

    with Image.open(path_raw) as img:
        # 透明图转 RGBA 保留 alpha；不透明图转 RGB，避免 WebP 带无用 alpha 通道
        preview_img = img.convert("RGBA" if _has_transparency(img) else "RGB")

        preview_img.thumbnail(preview_size, Image.Resampling.LANCZOS)
        # method=6 压缩率最高；RGBA 输入时 alpha 随 WebP 一起保存
        preview_img.save(path_preview, "WEBP", quality=85, method=6)

        return path_preview


async def generate_webp_images(slug_name: str, preview_size: Tuple[int, int] = (1200, 1200)) -> str:
    """生成 WebP 预览图；PNG/GIF 等透明图保留透明通道，返回预览图路径。

    解码/缩放/编码是 CPU + 磁盘密集操作，放到线程池执行，避免阻塞事件循环。
    """
    return await asyncio.to_thread(_generate_webp_sync, slug_name, preview_size)
