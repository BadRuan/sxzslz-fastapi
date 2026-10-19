from PIL import Image

from app.settings import UploadDir
from app.utils import genwebp
from app.utils.genwebp import generate_webp_images


def _upload_dirs(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    preview = tmp_path / "preview"
    raw.mkdir()
    preview.mkdir()
    monkeypatch.setattr(
        genwebp,
        "upload_dir",
        UploadDir(image_raw=str(raw), image_preview=str(preview), document=str(tmp_path)),
    )
    return raw


async def test_png_transparency_preserved(tmp_path, monkeypatch):
    """半透明 PNG 压缩为 WebP 后仍带 alpha（透明区域保持透明）"""
    raw = _upload_dirs(tmp_path, monkeypatch)
    img = Image.new("RGBA", (8, 8), (255, 0, 0, 0))
    img.putpixel((0, 0), (255, 0, 0, 255))
    img.save(raw / "a.png")

    out = await generate_webp_images("a.png")
    with Image.open(out) as webp:
        assert webp.mode == "RGBA"
        alpha_min, alpha_max = webp.getchannel("A").getextrema()
        assert alpha_min < 64  # 透明像素仍透明
        assert alpha_max == 255  # 不透明像素仍不透明


async def test_png_palette_transparency_preserved(tmp_path, monkeypatch):
    """调色板 PNG（tRNS 透明索引）压缩后同样保留透明"""
    raw = _upload_dirs(tmp_path, monkeypatch)
    img = Image.new("P", (8, 8), 0)
    palette = [255, 0, 0, 0, 255, 0] + [0, 0, 0] * 254
    img.putpalette(palette)
    img.putpixel((0, 0), 1)  # 一个不透明像素，其余为透明索引 0
    img.save(raw / "b.png", transparency=0)

    out = await generate_webp_images("b.png")
    with Image.open(out) as webp:
        assert webp.mode == "RGBA"
        alpha_min, alpha_max = webp.getchannel("A").getextrema()
        assert alpha_min < 64
        assert alpha_max == 255


async def test_gif_transparency_preserved(tmp_path, monkeypatch):
    """带透明索引的 GIF 压缩后仍带 alpha"""
    raw = _upload_dirs(tmp_path, monkeypatch)
    img = Image.new("P", (8, 8), 0)
    palette = [255, 0, 0, 0, 255, 0] + [0, 0, 0] * 254
    img.putpalette(palette)
    img.putpixel((0, 0), 1)  # 一个不透明像素，其余为透明索引 0
    img.save(raw / "c.gif", transparency=0)

    out = await generate_webp_images("c.gif")
    with Image.open(out) as webp:
        assert webp.mode == "RGBA"
        alpha_min, alpha_max = webp.getchannel("A").getextrema()
        assert alpha_min < 64
        assert alpha_max == 255


async def test_jpeg_opaque_output_has_no_alpha(tmp_path, monkeypatch):
    """无透明信息的 JPEG 输出为 RGB，不带多余 alpha 通道"""
    raw = _upload_dirs(tmp_path, monkeypatch)
    Image.new("RGB", (8, 8), (10, 20, 30)).save(raw / "d.jpg", "JPEG")

    out = await generate_webp_images("d.jpg")
    with Image.open(out) as webp:
        assert webp.mode == "RGB"


async def test_preview_downsized_within_bounds(tmp_path, monkeypatch):
    """预览图按 preview_size 缩放，超出部分等比缩小"""
    raw = _upload_dirs(tmp_path, monkeypatch)
    Image.new("RGB", (2400, 600), (1, 2, 3)).save(raw / "big.png")

    out = await generate_webp_images("big.png", preview_size=(1200, 1200))
    with Image.open(out) as webp:
        assert max(webp.size) <= 1200
        assert webp.size == (1200, 300)
