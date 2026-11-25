"""GET /logs/ 操作日志查询 API 测试。

覆盖：可见范围（匿名 401 / 普通用户只看本人 / 超管全量）、文章创建落日志、
过滤、分页、created_at 含时分秒、日志写失败不影响主业务。
"""

import re

from app.dao import OperationLogCrud


async def _seed_logs(session, count: int, *, operator_id: int = 1):
    """直接经 DAO 灌入 count 条日志（不走业务接口，便于控制过滤/分页数据）。"""
    for i in range(count):
        await OperationLogCrud(session).add(
            action="create_article",
            object_type="article",
            object_id=f"{i}",
            object_name=f"文章{i}",
            operator_id=operator_id,
            operator_name="操作人",
        )


async def test_logs_visibility_by_role(client, auth_headers, superadmin_headers):
    # 匿名 → 401
    resp = await client.get("/logs/")
    assert resp.status_code == 401
    # 普通用户 → 200（只看本人，范围由 test_normal_user_sees_only_own_logs 锁定）
    resp = await client.get("/logs/", headers=auth_headers)
    assert resp.status_code == 200
    # 超管 → 200
    resp = await client.get("/logs/", headers=superadmin_headers)
    assert resp.status_code == 200


async def test_normal_user_sees_only_own_logs(
    client, session, default_user, auth_headers, superadmin
):
    await _seed_logs(session, 2, operator_id=default_user.id)
    await _seed_logs(session, 2, operator_id=superadmin.id)

    resp = await client.get("/logs/", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert all(row["operator_id"] == default_user.id for row in body["data"])


async def test_normal_user_operator_id_param_ignored(
    client, session, default_user, auth_headers, superadmin
):
    await _seed_logs(session, 1, operator_id=default_user.id)
    await _seed_logs(session, 1, operator_id=superadmin.id)

    # 普通用户传他人 operator_id 也被强制收敛为本人（同 GET /articles/ 的 user_id 约定）
    resp = await client.get(
        "/logs/", params={"operator_id": superadmin.id}, headers=auth_headers
    )
    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["operator_id"] == default_user.id


async def test_log_created_at_includes_time(client, session, superadmin, superadmin_headers):
    await _seed_logs(session, 1, operator_id=superadmin.id)

    resp = await client.get("/logs/", headers=superadmin_headers)
    created_at = resp.json()["data"][0]["created_at"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", created_at), created_at


async def test_logs_recorded_on_article_create(client, session, superadmin, superadmin_headers):
    resp = await client.post(
        "/articles/", json={"title": "日志落库验证"}, headers=superadmin_headers
    )
    assert resp.status_code == 201

    resp = await client.get("/logs/", headers=superadmin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    first = body["data"][0]
    assert first["action"] == "create_article"
    assert first["object_type"] == "article"
    assert first["operator_id"] == superadmin.id
    assert first["operator_name"] == superadmin.nickname
    assert first["result"] == "success"


async def test_logs_filters(client, session, superadmin, superadmin_headers):
    await _seed_logs(session, 2, operator_id=superadmin.id)
    await OperationLogCrud(session).add(
        action="update_article",
        object_type="article",
        object_id="99",
        operator_id=superadmin.id,
        operator_name="超管",
    )
    await OperationLogCrud(session).add(
        action="create_document",
        object_type="document",
        object_id="d1",
        operator_id=superadmin.id,
        operator_name="超管",
    )

    # 按 action 过滤
    resp = await client.get("/logs/", params={"action": "update_article"}, headers=superadmin_headers)
    body = resp.json()
    assert body["total"] == 1
    assert all(row["action"] == "update_article" for row in body["data"])

    # 按 object_type 过滤
    resp = await client.get("/logs/", params={"object_type": "document"}, headers=superadmin_headers)
    body = resp.json()
    assert body["total"] == 1
    assert all(row["object_type"] == "document" for row in body["data"])

    # 按 operator_id 过滤（无匹配 → 空）
    resp = await client.get("/logs/", params={"operator_id": 999}, headers=superadmin_headers)
    body = resp.json()
    assert body["total"] == 0
    assert body["data"] == []


async def test_logs_pagination(client, session, superadmin_headers):
    await _seed_logs(session, 3)

    resp = await client.get(
        "/logs/", params={"page": 1, "page_size": 2}, headers=superadmin_headers
    )
    page1 = resp.json()
    assert page1["total"] == 3
    assert len(page1["data"]) == 2
    assert page1["has_next"] is True

    resp = await client.get(
        "/logs/", params={"page": 2, "page_size": 2}, headers=superadmin_headers
    )
    page2 = resp.json()
    assert page2["total"] == 3
    assert len(page2["data"]) == 1
    assert page2["has_next"] is False

    ids1 = [row["id"] for row in page1["data"]]
    ids2 = [row["id"] for row in page2["data"]]
    assert not set(ids1) & set(ids2), "两页不应有重复行"


async def test_log_write_failure_does_not_break_business(
    client, monkeypatch, superadmin_headers
):
    async def _boom(self, **kwargs):
        raise RuntimeError("日志表写入失败")

    monkeypatch.setattr("app.dao.operation_log.OperationLogCrud.add", _boom)

    resp = await client.post(
        "/articles/", json={"title": "日志写失败也要成功"}, headers=superadmin_headers
    )
    assert resp.status_code == 201


async def test_log_write_failure_does_not_leak_partial_rows(session, monkeypatch):
    """日志写失败（add 入会话后抛错）的半成品行不得随主事务提交（savepoint 隔离）。"""
    from sqlmodel import select

    from app.model.operation_log import OperationLog
    from app.service.operation_log import OperationService

    async def _half_written(self, **kwargs):
        session.add(
            OperationLog(action="create_article", object_type="article", object_id="boom")
        )
        raise RuntimeError("日志表写入失败")

    monkeypatch.setattr("app.dao.operation_log.OperationLogCrud.add", _half_written)
    await OperationService(session).log_operation(
        action="create_article", object_type="article", object_id="1"
    )
    await session.commit()  # 模拟请求会话的收尾 commit
    rows = (await session.exec(select(OperationLog))).all()
    assert list(rows) == [], "日志写失败的半成品行不应随主事务提交"
