"""媒体读取接口：附件 inline 开关、图片原图 raw 开关、以及公共缓存/安全头

对应 router 改动：
- GET /document/{slug}?inline=true → Content-Disposition: inline（供 iframe 预览），默认仍为 attachment
- GET /image/{slug}?raw=1       → 直接返回原图，等价于 ?file_type=raw
- 两者都带 Cache-Control 与 X-Content-Type-Options: nosniff
"""
import io

from PIL import Image

from app.settings import UploadDir


def _png_bytes(color=(0, 128, 255)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(buf, format="PNG")
    return buf.getvalue()


def _stub_dirs(tmp_path) -> UploadDir:
    raw, preview = tmp_path / "raw", tmp_path / "preview"
    raw.mkdir(exist_ok=True), preview.mkdir(exist_ok=True)
    return UploadDir(
        image_raw=str(raw),
        image_preview=str(preview),
        document=str(tmp_path / "doc"),
    )


async def _upload_document(client, auth_headers, tmp_path, monkeypatch):
    from app.routers import document as document_router
    from app.service import document as document_service

    stub = _stub_dirs(tmp_path)
    monkeypatch.setattr(document_service, "upload_dir", stub)
    monkeypatch.setattr(document_router, "upload_dir", stub)
    resp = await client.post(
        "/document/",
        files={"file": ("t.txt", b"hello", "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    return resp.json()["slug"]


async def _upload_image(client, auth_headers, tmp_path, monkeypatch):
    from app.routers import image as image_router
    from app.service import image as image_service
    from app.utils import genwebp

    stub = _stub_dirs(tmp_path)
    monkeypatch.setattr(image_service, "upload_dir", stub)
    monkeypatch.setattr(image_router, "upload_dir", stub)
    monkeypatch.setattr(genwebp, "upload_dir", stub)
    resp = await client.post(
        "/image/",
        files={"file": ("t.png", _png_bytes(), "image/png")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    return resp.json()["slug"]


async def test_document_defaults_to_attachment(client, auth_headers, tmp_path, monkeypatch):
    slug = await _upload_document(client, auth_headers, tmp_path, monkeypatch)

    resp = await client.get(f"/document/{slug}")
    assert resp.status_code == 200
    assert resp.headers["content-disposition"].startswith("attachment")
    assert resp.headers["cache-control"] == "public, max-age=604800"
    assert resp.headers["x-content-type-options"] == "nosniff"


async def test_document_inline_preview(client, auth_headers, tmp_path, monkeypatch):
    slug = await _upload_document(client, auth_headers, tmp_path, monkeypatch)

    resp = await client.get(f"/document/{slug}", params={"inline": "true"})
    assert resp.status_code == 200
    assert resp.headers["content-disposition"].startswith("inline")


async def test_image_preview_and_raw(client, auth_headers, tmp_path, monkeypatch):
    slug = await _upload_image(client, auth_headers, tmp_path, monkeypatch)

    preview = await client.get(f"/image/{slug}")
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/webp"
    assert preview.headers["cache-control"] == "public, max-age=604800"

    # 两种写法都应当拿到原图（PNG 而非 WebP）
    for query in ({"raw": "true"}, {"file_type": "raw"}):
        raw = await client.get(f"/image/{slug}", params=query)
        assert raw.status_code == 200
        assert raw.headers["content-type"] == "image/png"
        assert raw.headers["x-content-type-options"] == "nosniff"
        assert raw.content == _png_bytes()
