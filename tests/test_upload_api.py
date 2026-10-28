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
    body = resp.json()
    assert body["slug"].endswith(".png")
    assert body["size_bytes"] > 0
    assert body["url"] == f"/image/{body['slug']}"
    assert body["raw_url"] == f"/image/{body['slug']}?file_type=raw"


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
    body = resp.json()
    assert body["filename"] == "t.txt"
    assert body["size_bytes"] == 5
    assert body["url"] == f"/document/{body['slug']}"
    assert body["raw_url"] is None


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

    img_list = (await client.get("/image/", headers=auth_headers)).json()["data"][0]
    assert img_list["user_id"] == default_user.id
    assert img_list["user"]["nickname"] == "管理员"

    doc_list = (await client.get("/document/", headers=auth_headers)).json()["data"][0]
    assert doc_list["user_id"] == default_user.id
    assert doc_list["user"]["id"] == default_user.id


async def test_upload_document_too_large(client, auth_headers, tmp_path, monkeypatch):
    """超过 MAX_DOCUMENT_SIZE_MB → 400，半成品文件已清理"""
    from app.service import document as document_service_module
    from app.settings import settings

    doc_dir = tmp_path / "doc"
    monkeypatch.setattr(settings, "MAX_DOCUMENT_SIZE_MB", 0)  # 0MB → 任何非空文件超限
    monkeypatch.setattr(
        document_service_module,
        "upload_dir",
        UploadDir(image_raw=str(tmp_path / "r"), image_preview=str(tmp_path / "p"), document=str(doc_dir)),
    )
    resp = await client.post(
        "/document/",
        files={"file": ("big.txt", b"hello", "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "超过限制" in resp.json()["detail"]
    # 无半成品落盘、无脏数据入库
    assert (await client.get("/document/", headers=auth_headers)).json()["total"] == 0
    if doc_dir.exists():
        assert list(doc_dir.iterdir()) == []


async def test_upload_empty_file_rejected(client, auth_headers, tmp_path, monkeypatch):
    """空文件 → 400"""
    from app.service import document as document_service_module

    doc_dir = tmp_path / "doc"
    monkeypatch.setattr(
        document_service_module,
        "upload_dir",
        UploadDir(image_raw=str(tmp_path / "r"), image_preview=str(tmp_path / "p"), document=str(doc_dir)),
    )
    resp = await client.post(
        "/document/",
        files={"file": ("empty.txt", b"", "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "文件内容为空"


async def test_write_upload_stream_cleans_up_on_client_disconnect(tmp_path):
    """客户端中断上传：抛 ClientDisconnect 且半成品已清理"""
    from starlette.requests import ClientDisconnect

    from app.utils.io import write_upload_stream

    class _DisconnectingFile:
        async def read(self, size: int = -1) -> bytes:
            raise ClientDisconnect()

    target = tmp_path / "partial.bin"
    target.write_bytes(b"partial")
    try:
        await write_upload_stream(str(target), _DisconnectingFile())  # type: ignore[arg-type]
        raise AssertionError("应当抛出 ClientDisconnect")
    except ClientDisconnect:
        pass
    assert not target.exists()


def test_storage_error_from_classifies_oserror():
    """storage_error_from 把 ENOSPC / EACCES / 其他 OSError 映射为可读文案"""
    import errno

    from app.utils.io import StorageError, storage_error_from

    cases = [
        (errno.ENOSPC, "磁盘空间已满"),
        (errno.EACCES, "无写入权限"),
        (errno.EPERM, "无写入权限"),
        (errno.EIO, "保存到服务器失败"),
    ]
    for err_no, keyword in cases:
        mapped = storage_error_from(OSError(err_no, "os error"))
        assert isinstance(mapped, StorageError)
        assert keyword in str(mapped)


async def test_upload_document_disk_full(client, auth_headers, tmp_path, monkeypatch):
    """写盘时 ENOSPC → 400 磁盘空间已满，半成品已清理"""
    import errno

    import app.utils.io as io_module

    doc_dir = _stub_doc_upload_dir(tmp_path, monkeypatch)
    real_open = open

    def fake_open(file, mode="r", *args, **kwargs):
        fh = real_open(file, mode, *args, **kwargs)
        if "w" in mode:
            def failing_write(data):
                raise OSError(errno.ENOSPC, "No space left on device")
            fh.write = failing_write
        return fh

    monkeypatch.setattr(io_module, "open", fake_open, raising=False)
    resp = await client.post(
        "/document/",
        files={"file": ("t.txt", b"hello", "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "磁盘空间已满" in resp.json()["detail"]
    assert (await client.get("/document/", headers=auth_headers)).json()["total"] == 0
    if doc_dir.exists():
        assert list(doc_dir.iterdir()) == []


async def test_upload_document_permission_denied(
    client, auth_headers, tmp_path, monkeypatch
):
    """写盘时 EACCES → 400 无写入权限"""
    import errno

    import app.utils.io as io_module

    _stub_doc_upload_dir(tmp_path, monkeypatch)
    real_open = open

    def fake_open(file, mode="r", *args, **kwargs):
        if "w" in mode:
            raise OSError(errno.EACCES, "Permission denied")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(io_module, "open", fake_open, raising=False)
    resp = await client.post(
        "/document/",
        files={"file": ("t.txt", b"hello", "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "无写入权限" in resp.json()["detail"]
    assert (await client.get("/document/", headers=auth_headers)).json()["total"] == 0


async def test_upload_document_unsupported_type(client, auth_headers):
    """Content-Type 不在白名单 → 400，detail 带上实际收到的类型"""
    resp = await client.post(
        "/document/",
        files={"file": ("evil.exe", b"MZ", "application/x-msdownload")},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "application/x-msdownload" in detail
    assert "不支持的文件类型" in detail


async def test_upload_image_unsupported_type(client, auth_headers):
    """图片 Content-Type 不在白名单 → 400，detail 带上实际收到的类型"""
    resp = await client.post(
        "/image/",
        files={"file": ("t.heic", b"heic", "image/heic")},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "image/heic" in detail
    assert "不支持的图片类型" in detail


async def test_upload_image_bmp_allowed(client, auth_headers, tmp_path, monkeypatch):
    """BMP 在白名单内（PIL 可解码生成预览）"""
    from app.service import image as image_service_module
    from app.utils import genwebp

    raw, preview = tmp_path / "raw", tmp_path / "preview"
    raw.mkdir(), preview.mkdir()
    stub = UploadDir(image_raw=str(raw), image_preview=str(preview), document=str(tmp_path))
    monkeypatch.setattr(image_service_module, "upload_dir", stub)
    monkeypatch.setattr(genwebp, "upload_dir", stub)

    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (1, 2, 3)).save(buf, format="BMP")
    resp = await client.post(
        "/image/",
        files={"file": ("t.bmp", buf.getvalue(), "image/bmp")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["slug"].endswith(".bmp")


async def test_upload_document_new_common_types_accepted(
    client, auth_headers, tmp_path, monkeypatch
):
    """扩展白名单：csv / 7z / odt / epub / rar 等 MIME 可通过类型校验"""
    from app.service import document as document_service_module

    doc_dir = tmp_path / "doc"
    monkeypatch.setattr(
        document_service_module,
        "upload_dir",
        UploadDir(
            image_raw=str(tmp_path / "r"),
            image_preview=str(tmp_path / "p"),
            document=str(doc_dir),
        ),
    )
    cases = [
        ("a.csv", b"a,b\n1,2\n", "text/csv"),
        ("b.7z", b"7z\xbc\xaf'\x1c", "application/x-7z-compressed"),
        ("c.odt", b"PK\x03\x04odt", "application/vnd.oasis.opendocument.text"),
        ("d.epub", b"PK\x03\x04epub", "application/epub+zip"),
        ("e.rar", b"Rar!\x1a\x07\x00", "application/vnd.rar"),
    ]
    for name, content, mime in cases:
        resp = await client.post(
            "/document/",
            files={"file": (name, content, mime)},
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"{mime} 应被接受，实际 {resp.status_code}: {resp.text}"


async def test_upload_image_corrupt_content(
    client, auth_headers, tmp_path, monkeypatch
):
    """MIME 合法但内容损坏 → 400，原图半成品已清理、无脏数据入库"""
    from app.service import image as image_service_module
    from app.utils import genwebp

    raw, preview = tmp_path / "raw", tmp_path / "preview"
    raw.mkdir(), preview.mkdir()
    stub = UploadDir(image_raw=str(raw), image_preview=str(preview), document=str(tmp_path))
    monkeypatch.setattr(image_service_module, "upload_dir", stub)
    monkeypatch.setattr(genwebp, "upload_dir", stub)

    resp = await client.post(
        "/image/",
        files={"file": ("fake.png", b"not-a-real-png", "image/png")},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "不是有效的图片文件" in resp.json()["detail"]
    assert list(raw.iterdir()) == []
    assert (await client.get("/image/", headers=auth_headers)).json()["total"] == 0


def _stub_doc_upload_dir(tmp_path, monkeypatch):
    from app.service import document as document_service_module

    doc_dir = tmp_path / "doc"
    stub = UploadDir(
        image_raw=str(tmp_path / "r"),
        image_preview=str(tmp_path / "p"),
        document=str(doc_dir),
    )
    monkeypatch.setattr(document_service_module, "upload_dir", stub)
    return doc_dir


async def _upload_doc(client, auth_headers, content=b"hello", name="t.txt"):
    resp = await client.post(
        "/document/",
        files={"file": (name, content, "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    return resp.json()


async def test_delete_document_owner(client, auth_headers, tmp_path, monkeypatch):
    """本人删除成功：204、列表消失、磁盘文件已清理"""
    doc_dir = _stub_doc_upload_dir(tmp_path, monkeypatch)
    body = await _upload_doc(client, auth_headers)
    slug = body["slug"]
    assert (doc_dir / slug).is_file()

    resp = await client.delete(f"/document/{slug}", headers=auth_headers)
    assert resp.status_code == 204
    assert resp.content == b""
    assert not (doc_dir / slug).exists()
    assert (await client.get("/document/", headers=auth_headers)).json()["total"] == 0
    assert (
        await client.get(f"/document/{slug}", headers=auth_headers)
    ).status_code == 404


async def test_delete_document_requires_auth(client, auth_headers, tmp_path, monkeypatch):
    _stub_doc_upload_dir(tmp_path, monkeypatch)
    body = await _upload_doc(client, auth_headers)
    resp = await client.delete(f"/document/{body['slug']}")
    assert resp.status_code == 401


async def test_delete_document_unknown_slug_404(client, auth_headers):
    resp = await client.delete("/document/no-such.pdf", headers=auth_headers)
    assert resp.status_code == 404


async def test_delete_document_forbidden_for_other_user(
    client, session, default_user, auth_headers, tmp_path, monkeypatch
):
    """非上传者删除 → 403，记录与磁盘文件保留"""
    from app.auth import create_access_token
    from app.model import User

    doc_dir = _stub_doc_upload_dir(tmp_path, monkeypatch)
    body = await _upload_doc(client, auth_headers)
    slug = body["slug"]

    other = User.create_user(username="other", nickname="他人", password="test123")
    session.add(other)
    await session.flush()
    other_headers = {"Authorization": f"Bearer {create_access_token(other.id)}"}

    resp = await client.delete(f"/document/{slug}", headers=other_headers)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "无权限操作该文件"
    assert (doc_dir / slug).is_file()
    assert (
        await client.get("/document/", headers=auth_headers)
    ).json()["total"] == 1
    # 本人仍可删
    assert (await client.delete(f"/document/{slug}", headers=auth_headers)).status_code == 204


async def test_patch_document_rename_owner(client, auth_headers, tmp_path, monkeypatch):
    """本人改名成功：raw_filename 更新，下载头文件名同步"""
    from app.routers import document as document_router_module

    doc_dir = _stub_doc_upload_dir(tmp_path, monkeypatch)
    monkeypatch.setattr(
        document_router_module,
        "upload_dir",
        UploadDir(
            image_raw=str(tmp_path / "r"),
            image_preview=str(tmp_path / "p"),
            document=str(doc_dir),
        ),
    )
    body = await _upload_doc(client, auth_headers)
    slug = body["slug"]

    resp = await client.patch(
        f"/document/{slug}",
        json={"raw_filename": "新报告名.txt"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["raw_filename"] == "新报告名.txt"
    assert data["slug"] == slug  # slug 不变

    # 列表同步
    listed = (await client.get("/document/", headers=auth_headers)).json()["data"][0]
    assert listed["raw_filename"] == "新报告名.txt"

    # 下载 Content-Disposition 使用新文件名（非 ASCII 走 RFC 5987 filename*）
    download = await client.get(f"/document/{slug}", headers=auth_headers)
    assert download.status_code == 200
    disposition = download.headers.get("content-disposition", "")
    assert "attachment" in disposition
    assert "filename*=utf-8''" in disposition
    from urllib.parse import unquote

    encoded = disposition.split("filename*=utf-8''", 1)[1]
    assert unquote(encoded) == "新报告名.txt"


async def test_patch_document_forbidden_and_errors(
    client, session, auth_headers, tmp_path, monkeypatch
):
    """401 未登录；403 非本人；404 不存在；422 空文件名"""
    from app.auth import create_access_token
    from app.model import User

    _stub_doc_upload_dir(tmp_path, monkeypatch)
    body = await _upload_doc(client, auth_headers)
    slug = body["slug"]

    assert (
        await client.patch(f"/document/{slug}", json={"raw_filename": "x.txt"})
    ).status_code == 401
    assert (
        await client.patch(
            f"/document/{slug}", json={"raw_filename": "x.txt"}, headers=auth_headers
        )
    ).status_code == 200

    other = User.create_user(username="other2", nickname="他人2", password="test123")
    session.add(other)
    await session.flush()
    other_headers = {"Authorization": f"Bearer {create_access_token(other.id)}"}
    forbidden = await client.patch(
        f"/document/{slug}", json={"raw_filename": "hack.txt"}, headers=other_headers
    )
    assert forbidden.status_code == 403

    assert (
        await client.patch(
            "/document/no-such.pdf",
            json={"raw_filename": "x.txt"},
            headers=auth_headers,
        )
    ).status_code == 404
    assert (
        await client.patch(
            f"/document/{slug}", json={"raw_filename": ""}, headers=auth_headers
        )
    ).status_code == 422
