# 收尾 WIP（操作日志查询 + 文章无限滚动）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 schema 导出阻塞，补完两个 WIP 特性（`GET /articles/infinite` 无限滚动、`GET /logs/` 操作日志超管查询），补齐测试盲区与文档缺口，全量测试跑绿。

**Architecture:** 在既有分层（routers → service → dao → model）内补齐缺口：schema 导出修复让 WIP 代码可导入；无限滚动复用 `ArticleService.list_infinite`（已存在）并新增路由；操作日志在既有 `OperationService.log_operation` 写入侧之外补 dao/service 查询链与超管路由。响应分页复用 `PageResponse`。

**Tech Stack:** Python 3.12 + FastAPI + SQLModel（异步）+ pytest/pytest-asyncio（内存 SQLite）。

**Spec:** `docs/superpowers/specs/2026-11-25-finish-wip-design.md`

## Global Constraints

- 分层 `routers → service → dao → model`；DAO 只 flush，不 commit；`ServiceError`(ValueError) → 400 `{"detail": ...}`，路由层不 try/except。
- 新代码横切导入用 `app.core.*`（`app/auth.py` 等是兼容层）。
- 无 lint / typecheck / CI；不得引入。不新增依赖；不动 `requirements.txt`。
- 测试命令用 `.venv/bin/python -m pytest [路径] -q -p no:cacheprovider`（`uv run` 在本环境因缓存只读不可用）。测试函数直接 `async def`，无装饰器。
- `GET /articles/infinite` **必须注册在 `GET /articles/{slug}` 之前**（FastAPI 按注册顺序匹配，否则被 `{slug}` 吞掉）。
- 提交信息用中文短句（仓库既有惯例），每个 Task 一个 commit。
- 403 文案常量集中在 `app/types.py`。

## Review Focus

- 同一 `create_at` 时间戳的文章跨页翻页：游标 `(create_at, id)` 双键必须保证无重复、无遗漏（Task 2 测试钉住）。
- 普通用户传 `user_id` 想看他人文章：必须被收敛为本人，不泄露（Task 2 测试钉住）。
- 伪造 / 损坏的 `cursor`：返回 400 而不是 500（Task 2 测试钉住）。
- 日志写入失败（DB 异常）不影响主业务响应（Task 3 测试钉住：monkeypatch `OperationLogCrud.add` 抛异常，创建文章仍 201）。
- **失败日志随主事务回滚是已知取舍**（`app/service/operation_log.py` docstring 已写明）：任何测试不得断言「失败请求后日志行存在」——那行随 rollback 丢失；只能断言成功路径的落库。

---

### Task 1: 修复 schema 导出阻塞（WIP 可导入、测试可收集）

**Files:**
- Modify: `app/schema/__init__.py`（`from app.schema.common import` 处补导出，`__all__` 同步）
- Test: `tests/test_infinite_schema.py`（新建）

**Interfaces:**
- Produces: `app.schema` 顶层导出 `ArticleInfiniteOut`、`encode_cursor(create_at: Optional[datetime], id: int) -> str`、`decode_cursor(cursor: str) -> dict`（与 `app/schema/common.py` 中既有实现同名同签名）。

- [ ] **Step 1: 写失败测试** `tests/test_infinite_schema.py`：

```python
def test_infinite_schema_exported():
    from app.schema import ArticleInfiniteOut, decode_cursor, encode_cursor
    cur = encode_cursor(None, 42)
    assert decode_cursor(cur)["id"] == 42
```

- [ ] **Step 2: 跑测试确认失败**：`.venv/bin/python -m pytest tests/test_infinite_schema.py -q -p no:cacheprovider` → ImportError（收集即挂）。
- [ ] **Step 3: 改 `app/schema/__init__.py`**：`from app.schema.common import ArticleInfiniteOut, PageResponse, decode_cursor, encode_cursor, page_response`，并把三个新名字加进 `__all__`。
- [ ] **Step 4: 跑测试确认通过 + 全量可收集**：`.venv/bin/python -m pytest tests/test_infinite_schema.py -q -p no:cacheprovider` → PASS；`.venv/bin/python -m pytest -q -p no:cacheprovider --collect-only | tail -3` 无 ImportError。
- [ ] **Step 5: Commit**（连同既有 WIP 文件一起入库，这是该特性的基础层）：

```bash
git add app/schema/__init__.py tests/test_infinite_schema.py app/model/operation_log.py app/dao/operation_log.py app/service/operation_log.py
git add -u
git commit -m "修复 schema 导出阻塞并入库操作日志/无限滚动基础层"
```

### Task 2: `GET /articles/infinite` 无限滚动端点

**Files:**
- Modify: `app/routers/article.py`（新增路由，放在 `GET /stats` 之后、`GET /{slug}` 之前）
- Modify: `app/service/article.py:94`（`list_infinite` 内补 cursor 预校验 → `ServiceError("无效的游标")`）
- Test: `tests/test_article_infinite_api.py`（新建）

**Interfaces:**
- Consumes: `ArticleService.list_infinite(limit: int = DEFAULT_PAGE_SIZE, cursor: Optional[str] = None, category_id: Optional[int] = None, user_id: Optional[int] = None, is_deleted: bool = False, order_by_field: Literal["id", "create_at"] = "create_at", keyword: Optional[str] = None) -> ArticleInfiniteOut`（已存在，`app/service/article.py:94`）；`decode_cursor`（Task 1 导出）；路由内既有辅助 `_resolve_visible_user_id` / `_resolve_sort` / `_normalize_keyword`。
- Produces: `GET /articles/infinite?limit&cursor&category_id&user_id&is_deleted&keyword&sort` → `ArticleInfiniteOut{data, limit, has_more, next_cursor}`。`limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)`；可见范围与 `GET /articles/` 完全一致（匿名=公开全量、普通用户=强制本人、超管=全量可过滤）。

- [ ] **Step 1: 写失败测试** `tests/test_article_infinite_api.py`（用例及断言）：
 1. `test_infinite_pagination_no_dup_no_miss`：建 5 篇文章（其中 2 篇同一 `create_at` 时间戳，覆盖双键排序），`limit=2` 连续翻 3 页，合并 id 列表 == 全部 5 个、无重复；末页 `has_more=False` 且 `next_cursor=None`。
 2. `test_infinite_scoped_by_role`：普通用户建 1 篇、超管建 2 篇；普通用户 token 请求 `?user_id=<超管id>` 得到的 `data` 只含本人文章；匿名请求返回全部 3 篇。
 3. `test_infinite_keyword_and_category_filter`：`keyword` 多词 AND 过滤；`category_id` 只返回挂该二级分类的文章。
 4. `test_infinite_invalid_cursor_400`：`cursor=not-a-cursor` → 400，`detail == "无效的游标"`。
 5. `test_infinite_limit_bounds_422`：`limit=0` 与 `limit=101` 均 422。
- [ ] **Step 2: 跑测试确认失败**：`.venv/bin/python -m pytest tests/test_article_infinite_api.py -q -p no:cacheprovider` → 404（路由不存在）。
- [ ] **Step 3: 实现**：
 - `app/service/article.py` 的 `list_infinite` 开头：`if cursor: try: decode_cursor(cursor) except Exception: raise ServiceError("无效的游标")`（预校验；dao 内 decode 不再改）。
 - `app/routers/article.py` 新增 `@router.get("/infinite", response_model=ArticleInfiniteOut)`，参数按 Interfaces 签名（Query 约束同 `GET /articles/`），`current_user: Optional[User] = Depends(get_optional_user)`，调用 `service.list_infinite(limit, cursor, category_id, _resolve_visible_user_id(user_id, current_user), is_deleted, order_by_field=_resolve_sort(sort, current_user).value, keyword=_normalize_keyword(keyword))`。**注册位置必须在 `GET /{slug}` 之前**。
- [ ] **Step 4: 跑测试确认通过**：`.venv/bin/python -m pytest tests/test_article_infinite_api.py -q -p no:cacheprovider` → PASS。
- [ ] **Step 5: Commit**：`git add app/routers/article.py app/service/article.py tests/test_article_infinite_api.py && git commit -m "新增文章无限滚动端点 GET /articles/infinite"`

### Task 3: `GET /logs/` 操作日志超管查询

**Files:**
- Create: `app/schema/operation_log.py`（`OperationLogOut`）、`app/routers/operation_log.py`（`router`）
- Modify: `app/dao/operation_log.py`（补 `list_paginated`）、`app/service/operation_log.py`（补 `list_paginated`）、`app/schema/__init__.py`、`app/routers/__init__.py`（导出 `operation_log_router`）、`main.py`（挂载 `prefix="/logs"`）、`app/types.py`（`LOG_QUERY_FORBIDDEN = "仅超级管理员可查看操作日志"`）
- Test: `tests/test_operation_log_api.py`（新建）

**Interfaces:**
- Produces:
 - `OperationLogOut(BaseModel)`：`id:int, action:str, object_type:str, object_id:str, object_name:Optional[str], operator_id:Optional[int], operator_name:Optional[str], created_at:datetime, result:str, message:Optional[str], client_ip:Optional[str], user_agent:Optional[str]`。
 - `OperationLogCrud.list_paginated(*, action: Optional[str] = None, object_type: Optional[str] = None, operator_id: Optional[int] = None, result: Optional[str] = None, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE) -> Tuple[List[OperationLog], int]`（按 `created_at desc, id desc`，返回 (rows, total)）。
 - `OperationService.list_paginated(同上参数) -> PageResponse[OperationLogOut]`。
 - `GET /logs/`（仅超管，`Depends(require_superuser(LOG_QUERY_FORBIDDEN))`）查询参数：`page`(ge=1)、`page_size`(ge=1, le=MAX_PAGE_SIZE)、`action`、`object_type`、`operator_id`、`result`。

- [ ] **Step 1: 写失败测试** `tests/test_operation_log_api.py`：
 1. `test_logs_require_superuser`：匿名 → 401；普通用户 → 403；超管 → 200。
 2. `test_logs_recorded_on_article_create`：超管 `POST /articles/` 后 `GET /logs/`，`data[0]` 含 `action=="create_article"`、`operator_id` 为超管 id、`result=="success"`。
 3. `test_logs_filters`：按 `action` / `object_type` / `operator_id` 过滤只返回匹配行。
 4. `test_logs_pagination`：建 3 条日志，`page_size=2` 两页无重复、`total==3`。
 5. `test_log_write_failure_does_not_break_business`：monkeypatch `app.dao.operation_log.OperationLogCrud.add` 抛 `RuntimeError`，`POST /articles/` 仍 201。
- [ ] **Step 2: 跑测试确认失败**：`.venv/bin/python -m pytest tests/test_operation_log_api.py -q -p no:cacheprovider` → 404（`/logs/` 不存在）。
- [ ] **Step 3: 实现**：按 Interfaces 补 dao/service 查询（dao 用 `select(OperationLog)` + `func.count`，条件全部可选）；新建 `OperationLogOut`（字段映射 `OperationLog`）；新建路由文件（`from app.core.auth import require_superuser`，路由层不 try/except）；`app/routers/__init__.py` 导出、`main.py` 挂载（放 `user_router` 之后）、`app/types.py` 加常量。
- [ ] **Step 4: 跑测试确认通过**：`.venv/bin/python -m pytest tests/test_operation_log_api.py -q -p no:cacheprovider` → PASS。
- [ ] **Step 5: Commit**：`git add -A app/ main.py tests/test_operation_log_api.py && git commit -m "新增操作日志超管查询接口 GET /logs/"`

### Task 4: 测试盲区（分类 API 层、`GET /base/`）

**Files:**
- Test: `tests/test_category_api.py`、`tests/test_base_api.py`（新建）

**Interfaces:**
- Consumes: 既有 `POST/PATCH/DELETE /categories/`（仅超管写）、`GET /categories/`（公开）、`POST /articles/batch-category`（仅超管）、`GET /base/`（公开，分类树+用户列表）、`GET /base/storage`（需登录）。

- [ ] **Step 1: 写测试**（均为 API 层，覆盖行为而非重测 dao 已测逻辑）：
 - `tests/test_category_api.py`：① 分类写操作普通用户 403、匿名 401，文案 `仅超级管理员可管理文章分类`；② 超管建一/二级分类并 PATCH sort 后 `GET /categories/` 按 `sort, id` 升序；③ 试图建三级分类（parent 指向二级）→ 400；④ 删一级分类级联删除子分类且 `article_category` 关联被清理（文章本身不删）；⑤ `POST /articles/batch-category` 非法 slug 整批 400 不生效。
 - `tests/test_base_api.py`：① `GET /base/` 匿名 200，含分类树与用户列表字段；② `GET /base/storage` 匿名 401、登录 200 含容量字段（断言键存在即可，不断言具体数值）。
- [ ] **Step 2: 跑测试**：`.venv/bin/python -m pytest tests/test_category_api.py tests/test_base_api.py -q -p no:cacheprovider` → 全 PASS（这是补盲区，实现已存在；若有失败，按 systematic-debugging 定位真缺陷再修，不改测试迁就实现）。
- [ ] **Step 3: Commit**：`git add tests/test_category_api.py tests/test_base_api.py && git commit -m "补齐分类 API 与 /base 接口测试盲区"`

### Task 5: 文档补缺与杂项

**Files:**
- Modify: `README.md`、`docs/frontend-api.md`（补 4 个接口文档：`GET /articles/stats`、`GET /base/storage`、`GET /articles/infinite`、`GET /logs/`）
- Modify: `pyproject.toml`（description 改为 `FastAPI + SQLModel 异步内容 API（分类/文章/图片/文档 + JWT）`）
- Delete: `.patch_docs_sort.py`

**Interfaces:**
- Consumes: Task 2/3 的路由签名；既有 `GET /articles/stats`（`app/routers/article.py:205`，`ArticleStatsOut`，登录可见范围按 `_stats_window`）、`GET /base/storage`（`app/routers/base.py`，`StorageOut`）。写文档前先读这两个路由与 `app/service/article.py:273-320`、`app/schema/system.py`，文档中的字段/权限描述必须与实现一致。

- [ ] **Step 1: 补文档**：按既有 `docs/frontend-api.md` 的条目格式（方法/权限/参数/响应示例）各补一节；README 的接口清单表同步补行（含无限滚动游标翻页用法一段）。
- [ ] **Step 2: 杂项**：改 `pyproject.toml` description；`git rm .patch_docs_sort.py`（确认是遗留一次性脚本后删除）。
- [ ] **Step 3: 验证文档与实现一致**：对照路由实际 Query 参数逐条核对（stats/storage 是本次补写，重点核）。
- [ ] **Step 4: Commit**：`git add README.md docs/frontend-api.md pyproject.toml && git rm .patch_docs_sort.py && git commit -m "补齐 stats/storage/infinite/logs 接口文档并清理遗留脚本"`

### Task 6: 全量验证（verification-before-completion）

- [ ] **Step 1:** `.venv/bin/python -m pytest -q -p no:cacheprovider` 全量跑，记录通过数；任何失败回到对应 Task 修复。
- [ ] **Step 2:** `python -c "import main"` 冒烟（应用可启动）。
- [ ] **Step 3:** `git status` 确认工作区干净、无遗漏未跟踪文件（`sxzslz_fastapi.egg-info/` 已被 .gitignore 覆盖，不算）。
- [ ] **Step 4:** 汇总报告：完成项、测试证据（命令 + 通过数）、P2 遗留（Alembic 收口、operation_log 生产建表脚本、失败日志独立会话）。
