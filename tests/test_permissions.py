"""角色权限：超管（ruanfumin）全量管理；普通用户仅自己文章/上传文件"""
import io

from PIL import Image as PILImage

from app.model import User
from app.schema import ArticleCreate
from app.service import ArticleService
from app.settings import UploadDir
from app.utils import genwebp


async def _create_owned_article(session, owner: User, title: str = "归属文章"):
    service = ArticleService(session)
    return await service.create(ArticleCreate(title=title), user_id=owner.id)


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    PILImage.new("RGB", (8, 8), (0, 128, 255)).save(buf, format="PNG")
    return buf.getvalue()


# ---------- 文章：作者 / 超管改密权 ----------


async def test_patch_others_article_forbidden(client, session, default_user, superadmin, auth_headers):
    """普通用户改他人文章 → 403"""
    article = await _create_owned_article(session, superadmin, "超管的文章")
    resp = await client.patch(
        f"/articles/{article.slug}", json={"title": "偷改"}, headers=auth_headers
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "无权修改他人文章"


async def test_patch_own_article_ok(client, session, default_user, auth_headers):
    article = await _create_owned_article(session, default_user)
    resp = await client.patch(
        f"/articles/{article.slug}", json={"title": "自己的新标题"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "自己的新标题"


async def test_normal_user_cannot_change_author_or_create_at(
    client, session, default_user, superadmin, auth_headers
):
    """普通用户请求体带 user_id / create_at 会被忽略，只有正文类字段生效"""
    from datetime import datetime

    article = await _create_owned_article(session, default_user)
    resp = await client.patch(
        f"/articles/{article.slug}",
        json={
            "title": "改标题",
            "user_id": superadmin.id,
            "create_at": "2000-01-01T00:00:00",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "改标题"
    assert data["user_id"] == default_user.id  # 作者未变
    assert data["create_at"] != "2000-01-01T00:00:00"  # 发布时间未变


async def test_superadmin_can_change_author_and_create_at(
    client, session, default_user, superadmin, superadmin_headers
):
    """超管可改任意文章的作者与发布时间"""
    article = await _create_owned_article(session, default_user, "待接管")
    resp = await client.patch(
        f"/articles/{article.slug}",
        json={
            "title": "超管改",
            "user_id": superadmin.id,
            "create_at": "2020-06-01T08:30:00",
        },
        headers=superadmin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "超管改"
    assert data["user_id"] == superadmin.id
    assert data["create_at"].startswith("2020-06-01T08:30:00")


async def test_view_and_like_count_not_patchable(
    client, session, default_user, superadmin, superadmin_headers
):
    """view_count / like_count 不在 PATCH 字段中：传入会被模型忽略（额外字段不进 schema）"""
    article = await _create_owned_article(session, default_user)
    resp = await client.patch(
        f"/articles/{article.slug}",
        json={"title": "t", "view_count": 9999, "like_count": 8888},
        headers=superadmin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["view_count"] != 9999
    assert resp.json()["like_count"] != 8888


async def test_delete_others_article_forbidden(client, session, superadmin, auth_headers):
    article = await _create_owned_article(session, superadmin)
    assert (
        await client.delete(f"/articles/{article.slug}", headers=auth_headers)
    ).status_code == 403


async def test_superadmin_can_delete_others_article(
    client, session, default_user, superadmin_headers
):
    article = await _create_owned_article(session, default_user)
    assert (
        await client.delete(f"/articles/{article.slug}", headers=superadmin_headers)
    ).status_code == 204


async def test_superadmin_can_create_at_and_author(
    client, session, superadmin, superadmin_headers
):
    """超管创建可同时指定作者与发布时间"""
    from app.model import User

    other = User.create_user(username="writer", nickname="写手", password="test123")
    session.add(other)
    await session.flush()
    resp = await client.post(
        "/articles/",
        json={
            "title": "定时发布",
            "user_id": other.id,
            "create_at": "2019-12-31T23:59:59",
        },
        headers=superadmin_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["user_id"] == other.id
    assert data["create_at"].startswith("2019-12-31T23:59:59")


# ---------- 图片 / 文档：列表可见范围与改删 ----------


def _stub_upload_dirs(tmp_path, monkeypatch):
    from app.routers import document as document_router_module
    from app.routers import image as image_router_module
    from app.service import document as document_service_module
    from app.service import image as image_service_module

    raw, preview, doc = tmp_path / "raw", tmp_path / "preview", tmp_path / "doc"
    raw.mkdir(), preview.mkdir(), doc.mkdir()
    stub = UploadDir(
        image_raw=str(raw), image_preview=str(preview), document=str(doc)
    )
    monkeypatch.setattr(image_service_module, "upload_dir", stub)
    monkeypatch.setattr(document_service_module, "upload_dir", stub)
    monkeypatch.setattr(image_router_module, "upload_dir", stub)
    monkeypatch.setattr(document_router_module, "upload_dir", stub)
    monkeypatch.setattr(genwebp, "upload_dir", stub)
    return stub


async def _upload_image(client, headers, name="t.png"):
    resp = await client.post(
        "/image/", files={"file": (name, _png_bytes(), "image/png")}, headers=headers
    )
    assert resp.status_code == 200
    return resp.json()


async def _upload_doc(client, headers, name="t.txt", content=b"hello"):
    resp = await client.post(
        "/document/",
        files={"file": (name, content, "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 200
    return resp.json()


async def test_file_list_requires_auth(client, auth_headers, tmp_path, monkeypatch):
    _stub_upload_dirs(tmp_path, monkeypatch)
    assert (await client.get("/image/")).status_code == 401
    assert (await client.get("/document/")).status_code == 401


async def test_image_document_list_scoped_by_owner(
    client, session, default_user, superadmin, auth_headers, superadmin_headers, tmp_path, monkeypatch
):
    """普通用户只看到自己的上传；超管看到全部"""
    _stub_upload_dirs(tmp_path, monkeypatch)
    mine_img = await _upload_image(client, auth_headers, "mine.png")
    await _upload_image(client, superadmin_headers, "super.png")
    mine_doc = await _upload_doc(client, auth_headers, "mine.txt")
    await _upload_doc(client, superadmin_headers, "super.txt")

    my_images = (await client.get("/image/", headers=auth_headers)).json()
    assert my_images["total"] == 1
    assert my_images["data"][0]["slug"] == mine_img["slug"]

    super_images = (await client.get("/image/", headers=superadmin_headers)).json()
    assert super_images["total"] == 2

    my_docs = (await client.get("/document/", headers=auth_headers)).json()
    assert my_docs["total"] == 1
    assert my_docs["data"][0]["slug"] == mine_doc["slug"]

    super_docs = (await client.get("/document/", headers=superadmin_headers)).json()
    assert super_docs["total"] == 2


async def test_document_download_scoped(
    client, session, default_user, superadmin, auth_headers, superadmin_headers, tmp_path, monkeypatch
):
    """文档下载：本人/超管可下，他人 403"""
    _stub_upload_dirs(tmp_path, monkeypatch)
    other_doc = await _upload_doc(client, superadmin_headers, "s.txt")

    assert (
        await client.get(f"/document/{other_doc['slug']}", headers=auth_headers)
    ).status_code == 403
    assert (
        await client.get(f"/document/{other_doc['slug']}", headers=superadmin_headers)
    ).status_code == 200
    assert (
        await client.get(f"/document/{other_doc['slug']}")
    ).status_code == 401


async def test_image_public_get_still_open(
    client, auth_headers, tmp_path, monkeypatch
):
    """图片本体保持公开（文章封面依赖）"""
    _stub_upload_dirs(tmp_path, monkeypatch)
    body = await _upload_image(client, auth_headers)
    assert (await client.get(f"/image/{body['slug']}")).status_code == 200


async def test_image_rename_and_delete_owner(
    client, auth_headers, tmp_path, monkeypatch
):
    _stub_upload_dirs(tmp_path, monkeypatch)
    body = await _upload_image(client, auth_headers)

    renamed = await client.patch(
        f"/image/{body['slug']}",
        json={"raw_filename": "新名字.png"},
        headers=auth_headers,
    )
    assert renamed.status_code == 200
    assert renamed.json()["raw_filename"] == "新名字.png"

    deleted = await client.delete(f"/image/{body['slug']}", headers=auth_headers)
    assert deleted.status_code == 204
    assert (await client.get("/image/", headers=auth_headers)).json()["total"] == 0


async def test_image_modify_others_forbidden(
    client, session, default_user, superadmin, auth_headers, superadmin_headers, tmp_path, monkeypatch
):
    _stub_upload_dirs(tmp_path, monkeypatch)
    super_img = await _upload_image(client, superadmin_headers)

    forbidden = await client.patch(
        f"/image/{super_img['slug']}",
        json={"raw_filename": "hack.png"},
        headers=auth_headers,
    )
    assert forbidden.status_code == 403

    assert (
        await client.delete(f"/image/{super_img['slug']}", headers=auth_headers)
    ).status_code == 403

    # 超管可删任意
    assert (
        await client.delete(f"/image/{super_img['slug']}", headers=superadmin_headers)
    ).status_code == 204


async def test_document_rename_and_delete_by_superuser(
    client, session, default_user, auth_headers, superadmin_headers, tmp_path, monkeypatch
):
    """超管可改名/删除他人文档"""
    _stub_upload_dirs(tmp_path, monkeypatch)
    my_doc = await _upload_doc(client, auth_headers, "personal.txt")

    renamed = await client.patch(
        f"/document/{my_doc['slug']}",
        json={"raw_filename": "超管改名.txt"},
        headers=superadmin_headers,
    )
    assert renamed.status_code == 200
    assert renamed.json()["raw_filename"] == "超管改名.txt"

    assert (
        await client.delete(f"/document/{my_doc['slug']}", headers=superadmin_headers)
    ).status_code == 204


async def test_user_out_exposes_is_superuser(client, default_user, superadmin, auth_headers, superadmin_headers):
    """/base/ 用户列表带 is_superuser，前端可据此区分角色"""
    resp = await client.get("/base/")
    users = {u["id"]: u for u in resp.json()["user"]}
    assert users[default_user.id]["is_superuser"] is False
    assert users[superadmin.id]["is_superuser"] is True
