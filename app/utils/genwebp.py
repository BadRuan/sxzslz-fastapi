from typing import NamedTuple
from os import path
from PIL import Image
from app.settings import upload_dir


class Dist_Dir(NamedTuple):
    preview: str

async def generate_webp_images(slug_name: str, preview_size=(1200, 1200)) -> Dist_Dir:
    """
    压缩图片并生成 WebP 格式的预览图和缩略图
    返回一个字典，包含生成的预览图和缩略图的文件名
    """
    slug, _ = path.splitext(slug_name)
    path_raw = path.join(upload_dir.image_raw, slug_name)
    path_preview = path.join(upload_dir.image_preview, slug + '.webp')

    with Image.open(path_raw) as img:
        # 统一转为 RGB（处理 PNG 透明通道问题）
        img_rgb = img.convert("RGB")

        # 生成网页预览图
        preview_img = img_rgb.copy()
        preview_img.thumbnail(preview_size, Image.Resampling.LANCZOS)
        preview_img.save(path_preview, "WEBP", quality=85, method=6) # method=6 压缩率最高
      
        return Dist_Dir(preview=path_preview)
