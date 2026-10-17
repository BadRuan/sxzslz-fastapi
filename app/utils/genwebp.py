from os import path

from PIL import Image

from app.settings import upload_dir


async def generate_webp_images(slug_name: str, preview_size=(1200, 1200)) -> str:
    """生成 WebP 预览图，返回预览图路径。"""
    slug, _ = path.splitext(slug_name)
    path_raw = path.join(upload_dir.image_raw, slug_name)
    path_preview = path.join(upload_dir.image_preview, slug + ".webp")

    with Image.open(path_raw) as img:
        # 统一转为 RGB（处理 PNG 透明通道问题）
        img_rgb = img.convert("RGB")

        preview_img = img_rgb.copy()
        preview_img.thumbnail(preview_size, Image.Resampling.LANCZOS)
        # method=6 压缩率最高
        preview_img.save(path_preview, "WEBP", quality=85, method=6)

        return path_preview
