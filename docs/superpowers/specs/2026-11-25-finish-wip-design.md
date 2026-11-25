# 收尾 WIP：操作日志查询 + 文章无限滚动 设计文档（短稿）

> 已与用户对齐（2026-11-25）：无限滚动挂新端点 `GET /articles/infinite`；操作日志补超管查询口。范围 P0+P1（P2 的 Alembic 收口与生产建表脚本本次不动）。

## 意图与背景

工作区有两个未提交的 WIP 特性（约 70%/60% 完成）：操作日志（已织入 service 层，无查询口）与文章无限滚动（dao/service 已完成，无路由）。且 `app/schema/__init__.py` 未导出 `ArticleInfiniteOut`，导致 `import main` 即挂、测试无法收集。本次收尾使两个特性可交付、测试全绿、文档补齐。

## 目标 / 非目标

**目标**
1. 修复 schema 导出阻塞（`ArticleInfiniteOut` / `encode_cursor` / `decode_cursor`）。
2. `GET /articles/infinite`：无限滚动端点，复用 `GET /articles/` 的可见范围（匿名=公开全量 / 普通=仅本人 / 超管=全量）、keyword、category_id、is_deleted、sort 规则；响应 `ArticleInfiniteOut`。
3. `GET /logs/`：操作日志查询，仅超管；分页 + action / object_type / operator_id / result 过滤；新到旧排序。
4. 补测试盲区（分类 API 层、`GET /base/`）与文档缺口（`GET /articles/stats`、`GET /base/storage` 及本次新端点）。
5. 杂项：pyproject description、删除遗留脚本 `.patch_docs_sort.py`。

**非目标（P2，另行决策）**
- Alembic 收口（引入或移除）；operation_log 生产库建表脚本；失败日志随主事务回滚的独立会话改造（docstring 已写明取舍，保持现状）。

## 已定做法（Approaches）

| 决策点 | 备选 | 选定 | 理由 |
|---|---|---|---|
| 无限滚动挂载 | A. 新端点 `/articles/infinite`；B. 并入 `GET /articles/` 加 cursor | **A**（用户确认） | B 需要一条路由两种响应形状，OpenAPI 与前端契约都不干净 |
| 日志查询 | A. 补 `GET /logs/` 超管查询；B. 只落库暂不查 | **A**（用户确认） | 没有查询口的审计日志等于白记；工作量小 |
| 日志事务 | 独立会话 vs 随主事务 | **随主事务**（现状） | 符合 `get_session` 统一 commit 约定；独立会话在测试环境复杂度高，留待有强审计需求再改 |
| 非法游标 | 422 vs 400 | **400** `ServiceError("无效的游标")` | 与项目「业务校验错误 → 400」约定一致 |
| limit 越界 | 钳制 vs 422 | **422**（路由 `ge=1, le=MAX_PAGE_SIZE`） | 与 `GET /articles/` 的 page_size 行为一致；service 内钳制保留作直调兜底 |

## 关键约束（继承 AGENTS.md）

- 分层 `routers → service → dao → model`；DAO 只 flush；`ServiceError` → 400。
- 新路由 `GET /articles/infinite` **必须注册在 `GET /articles/{slug}` 之前**，否则被路径参数吞掉。
- 不引入新依赖、不动 requirements.txt、不加 lint/CI。
- 测试：`async def` 直写（asyncio_mode=auto），内存 SQLite。

## 留给实现者

测试夹具复用 `tests/conftest.py` 现有 `client` / `auth_headers` / `default_user` / 超管夹具命名惯例；日志查询的响应字段按 `OperationLog` 模型全量映射（id/action/object_type/object_id/object_name/operator_id/operator_name/created_at/result/message/client_ip/user_agent）。
