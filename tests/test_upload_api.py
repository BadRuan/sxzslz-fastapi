"""上传接口鉴权：写操作需 Bearer（401），登录后上传成功（文件落盘走临时目录）"""
import io

from PIL import Image

from app.settings import UploadDir
from app.utils import genwebp


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (0, 128, 255)).save(buf, format="PNG")
    return buf.getvalue()


async def test_upload_image_requires_auth(client):
    resp = await client.post(
        "/image/", files={"file": ("t.png", _png_bytes(), "image/png")}
    )
    assert resp.status_code == 401


async def test_upload_document_requires_auth(client):
    resp = await client.post(
        "/document/", files={"file": ("t.txt", b"hello", "text/plain")}
    )
    assert resp.status_code == 401


async def test_upload_image_with_auth(client, auth_headers, tmp_path, monkeypatch):
    from app.service import image as image_service_module

    raw, preview = tmp_path / "raw", tmp_path / "preview"
    raw.mkdir(), preview.mkdir()
    stub = UploadDir(image_raw=str(raw), image_preview=str(preview), document=str(tmp_path))
    monkeypatch.setattr(image_service_module, "upload_dir", stub)
    monkeypatch.setattr(genwebp, "upload_dir", stub)

    resp = await client.post(
        "/image/",
        files={"file": ("t.png", _png_bytes(), "image/png")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["slug"].endswith(".png")


async def test_upload_document_with_auth(client, auth_headers, tmp_path, monkeypatch):
    from app.service import document as document_service_module

    doc_dir = tmp_path / "doc"
    monkeypatch.setattr(
        document_service_module,
        "upload_dir",
        UploadDir(image_raw=str(tmp_path / "r"), image_preview=str(tmp_path / "p"), document=str(doc_dir)),
    )
    resp = await client.post(
        "/document/",
        files={"file": ("t.txt", b"hello", "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["filename"] == "t.txt"
