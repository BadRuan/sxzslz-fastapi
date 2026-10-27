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


async def test_upload_records_uploader(client, session, default_user, auth_headers, tmp_path, monkeypatch):
    """上传者落库：列表返回 user_id 与嵌入的 user 对象"""
    from app.service import document as document_service_module
    from app.service import image as image_service_module

    raw, preview = tmp_path / "raw", tmp_path / "preview"
    raw.mkdir(), preview.mkdir()
    stub = UploadDir(image_raw=str(raw), image_preview=str(preview), document=str(tmp_path / "doc"))
    monkeypatch.setattr(image_service_module, "upload_dir", stub)
    monkeypatch.setattr(document_service_module, "upload_dir", stub)
    from app.utils import genwebp
    monkeypatch.setattr(genwebp, "upload_dir", stub)

    img_resp = await client.post(
        "/image/",
        files={"file": ("t.png", _png_bytes(), "image/png")},
        headers=auth_headers,
    )
    assert img_resp.status_code == 200
    doc_resp = await client.post(
        "/document/",
        files={"file": ("t.txt", b"hello", "text/plain")},
        headers=auth_headers,
    )
    assert doc_resp.status_code == 200

    img_list = (await client.get("/image/")).json()["data"][0]
    assert img_list["user_id"] == default_user.id
    assert img_list["user"]["nickname"] == "管理员"

    doc_list = (await client.get("/document/")).json()["data"][0]
    assert doc_list["user_id"] == default_user.id
    assert doc_list["user"]["id"] == default_user.id
