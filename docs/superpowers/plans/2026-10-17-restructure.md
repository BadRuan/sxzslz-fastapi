# sxzslz-fastapi 深度梳理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 理顺模块划分与层间边界，修掉已知缺陷，补关键注释，同步 README / AGENTS.md。

**Architecture:** 保持 `routers → service → dao → model` 分层不变，把 schema 拆成按领域分文件的包、Category 模型独立成文件、DAO 只返回 ORM 模型、service 统一组装 `PageResponse`。行为面只有 image/document 分页 `has_next` 一处变化。

**Tech Stack:** Python 3.12、FastAPI、SQLModel、pydantic-settings、Alembic、uv、pytest / ruff / pyright

**Spec:** `docs/superpowers/specs/2026-10-17-restructure-design.md`

## Global Constraints

- 不改数据库表结构、不写新迁移、不增删依赖。
- 对外路由路径、请求体、响应体 JSON 结构不变（`has_next` 真实值除外）。
- image/document 上传**保持匿名**，不加 Bearer 鉴权（用户明确决定）。
- DAO 不 import `app.schema`；DAO 只 `flush`，`get_session` 自动 commit。
- 业务校验错误：service 抛 `ValueError` → router 转 400 `{"detail": "..."}`。
- 注释只写非显然的 WHY（中文），不写「这行在干什么」。
- 每个 task 结束跑 `uv run pytest`，全绿才能 commit。
- 提交信息用 Conventional Commits。

## Review Focus

1. **`from app.schema import X` 兼容性** — 拆包后所有既有 import 必须仍然可用，漏一处就是 ImportError。→ Task 1 的全量测试即为该测试。
2. **image/document 分页 `has_next` + 预览图删除** — `has_next` 边界：`page * page_size == total` 时为 `false`，`total == 0` 时为 `false`；`remove_by_slug` 在 raw 缺失时也必须删预览图，否则泄漏。→ Task 5 测试覆盖。
3. **DAO 分层回归** — 若某处仍从 DAO 返回 `PageResponse`/`UserOut`，service 会二次包装或类型错乱。→ Task 4 的 ruff/pyright + 测试。
4. **软删除 / 层级 path 注释与实现一致** — 注释若描述了错误语义，比没有注释更糟。→ Task 7 自查对照 `category.py` 实现。
5. **文档与真实命令** — README/AGENTS.md 里每条命令必须可执行，结构树必须与目录一致。→ Task 8 逐条执行验证。

---

### Task 1: schema 拆包

**Files:**
- Create: `app/schema/__init__.py`、`app/schema/common.py`、`app/schema/auth.py`、`app/schema/user.py`、`app/schema/category.py`、`app/schema/article.py`、`app/schema/file.py`
- Delete: `app/schema.py`
- Test: 现有测试全量（无新测试；本 task 的交付就是 import 兼容 + 测试全绿）

**Interfaces:**
- Consumes: 现有 `app/schema.py` 中的全部类
- Produces: `from app.schema import <Name>` 对下列名字继续有效：`PageResponse`、`UserOut`、`LoginRequest`、`TokenOut`、`CategoryTree`、`CategoryOut`、`CategoryCreate`、`CategoryUpdate`、`ArticleOut`、`ArticleDetailOut`、`ArticleCreate`、`ArticleUpdate`。新文件 `app/schema/file.py` 本 task 只放占位的 `ImageOut` / `DocumentOut` / `UploadResult`（字段见 Step 3），供 Task 4–6 使用。

- [ ] **Step 1: 创建 `app/schema/common.py`**

放入 `PageResponse[T]`（保留 PEP 695 泛型语法），删除原文件里未使用的 `T = TypeVar("T")`。

- [ ] **Step 2: 按领域拆出其余 schema 文件**

| 文件 | 类 |
|---|---|
| `auth.py` | `LoginRequest`、`TokenOut` |
| `user.py` | `UserOut` |
| `category.py` | `CategoryTree`、`CategoryOut`、`CategoryCreate`、`CategoryUpdate` |
| `article.py` | `ArticleOut`、`ArticleDetailOut`、`ArticleCreate`、`ArticleUpdate`（`ArticleOut`/`ArticleDetailOut` 从 `common` 导入 `CategoryTree`、从 `user` 导入 `UserOut`） |
| `file.py` | `ImageOut`、`DocumentOut`、`UploadResult` |

`ImageOut` 字段：`id: int`、`slug: str`、`raw_filename: str`、`mime_type: str`、`size_bytes: int`、`view: int`、`uploaded_at: datetime`。
`DocumentOut` 同 `ImageOut`。
`UploadResult` 字段：`filename: str`、`slug: str`、`content_type: str`（对应现有上传响应 dict 的三个键，JSON 不变）。

三者都设 `model_config = ConfigDict(from_attributes=True)`。

- [ ] **Step 3: 写 `app/schema/__init__.py` 聚合导出**

显式 `from .xxx import ...` + `__all__` 列出上表全部名字。删除 `app/schema.py`。

- [ ] **Step 4: 运行全量测试验证 import 兼容**

Run: `uv run pytest`
Expected: 全部 PASS（与改动前基线一致）

- [ ] **Step 5: Commit**

```bash
git add app/schema
git rm app/schema.py
git commit -m "refactor(schema): split flat schema.py into domain package"
```

---

### Task 2: model 重组

**Files:**
- Create: `app/model/category.py`
- Modify: `app/model/article.py`、`app/model/user.py`、`app/model/image.py`、`app/model/document.py`、`app/model/__init__.py`
- Test: 现有测试全量

**Interfaces:**
- Consumes: Task 1 的 `CategoryTree`（`app/schema/category.py`）
- Produces: `app.model` 导出不变（`Article`、`ArticleCategory`、`Category`、`Document`、`Image`、`User`）；`Category` 定义移动到 `app/model/category.py`；各模型统一用模块级 `generate_slug()` 生成 slug。

- [ ] **Step 1: 把 `Category` 与 `ArticleCategory` 拆开**

`Category` 类 + 其 `__table_args__` / `Relationship` 移到 `app/model/category.py`。`ArticleCategory` 留在 `app/model/article.py`。`model/article.py` 里对 `Category` 的引用改为 `from app.model.category import Category`（注意避免循环 import：`category.py` 只在 `TYPE_CHECKING` 下引用 `Article`）。

- [ ] **Step 2: 统一 slug 生成命名**

`app/model/article.py` 与 `app/model/user.py` 已有模块级 `generate_slug()`，保留。`app/model/image.py` 与 `app/model/document.py` 的 `gen_slug` staticmethod 改为模块级 `generate_slug()`，长度保持 32 hex（`uuid4().hex`）。字段 `default_factory` 同步。

- [ ] **Step 3: 运行全量测试**

Run: `uv run pytest`
Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add app/model
git commit -m "refactor(model): extract Category model and unify generate_slug naming"
```

---

### Task 3: 死代码清理与命名修正

**Files:**
- Delete: `app/utils/file.py`、`app/utils/logger.py`
- Modify: `app/utils/__init__.py`、`app/utils/genwebp.py`、`app/settings.py`、`app/dao/user.py`、`app/dao/image.py`、`app/dao/document.py`、`app/dao/category.py`、`app/service/image.py`、`app/service/document.py`

**Interfaces:**
- Consumes: 无
- Produces: `app.settings.UploadDir`、`app.settings.AllowType`（替代 `IMAGE_DIR` / `ALLOW_TYPE`）；`app.utils.generate_webp_images(slug_name: str, preview_size=(1200, 1200)) -> str`（返回预览图路径，替代 `Dist_Dir`）；`DocumentCrud.record_view(slugname: str) -> None`（替代 `get_view`）。

- [ ] **Step 1: 删除未使用工具与 DAO 死方法**

删除 `utils/file.py`、`utils/logger.py`，`utils/__init__.py` 只导出 `generate_webp_images`。
删除 `UserCrud.get_by_id` / `get_count`、`ImageCrud.get_count` / `get_view`、`DocumentCrud.get_count` / `get_download`、`CategoryCrud.get_by_id`。`dao/user.py` 顶部多余的 `PasswordHasher` 实例一并删除（登录走 `user.check_password`）。

- [ ] **Step 2: 命名修正**

- `app/settings.py`：`IMAGE_DIR` → `UploadDir`，`ALLOW_TYPE` → `AllowType`（NamedTuple 类名）。
- `app/utils/genwebp.py`：删 `Dist_Dir`，函数返回 `str`（预览图路径）；docstring 改为一行说明。
- `DocumentCrud.get_view` → `DocumentCrud.record_view`；`app/service/document.py` 调用点同步。
- `app/service/image.py` 与 `app/service/document.py`：`suffiex` → `suffix`。

- [ ] **Step 3: 运行全量测试**

Run: `uv run pytest`
Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add -A app
git commit -m "chore: drop dead code and fix naming (UploadDir, record_view, suffix)"
```

---

### Task 4: DAO 层边界 — 不再返回 schema

**Files:**
- Modify: `app/dao/image.py`、`app/dao/document.py`、`app/dao/user.py`、`app/dao/category.py`
- Test: 现有测试全量（`tests/test_category_dao.py` 等若因 `get_by_id` 删除而引用需同步改）

**Interfaces:**
- Consumes: Task 2 的模型、Task 3 的 `record_view`
- Produces:
  - `ImageCrud.list_paginated(page: int, page_size: int) -> tuple[list[Image], int]`
  - `DocumentCrud.list_paginated(page: int, page_size: int) -> tuple[list[Document], int]`
  - `UserCrud.get_all() -> list[User]`（已如此，保持）
  - `CategoryCrud.get_tree_all() -> list[CategoryTree]` — **例外保留**：树形组装需要 schema 的 `children` 递归结构，留在 DAO；`dao/category.py` 对 `CategoryTree` 的 import 标注为「树形输出需要，schema 仅作只读投影」。

- [ ] **Step 1: 改 `ImageCrud.list_paginated` / `DocumentCrud.list_paginated` 返回 `(list, total)`**

去掉 DAO 内的 `PageResponse` 组装；`DocumentCrud.list_paginated` 保持按 `desc(Document.view)` 排序，`ImageCrud` 保持 `desc(Image.id)`。

- [ ] **Step 2: 改 `UserCrud.get_by_username` 保持返回 `User`（已是）；删除对 `UserOut` 的 import**

- [ ] **Step 3: 运行测试，修掉因删除死方法导致的测试引用**

Run: `uv run pytest`
Expected: 全部 PASS（若 `tests/test_category_dao.py` 调用了已删的 `get_by_id`，改用 `get_raw_by_id` 或删除对应断言）

- [ ] **Step 4: Commit**

```bash
git add app/dao tests
git commit -m "refactor(dao): return ORM models instead of schemas from list_paginated"
```

---

### Task 5: service 收口 + has_next 修复

**Files:**
- Modify: `app/service/image.py`、`app/service/document.py`
- Test: `tests/test_file_service_pagination.py`（新建）

**Interfaces:**
- Consumes: Task 4 的 `(list, total)`；Task 1 的 `PageResponse`、`ImageOut`、`DocumentOut`
- Produces:
  - `ImageService.list_paginated(page: int, page_size: int) -> PageResponse[ImageOut]`
  - `DocumentService.list_paginated(page: int, page_size: int) -> PageResponse[DocumentOut]`

- [ ] **Step 1: 写失败测试 `tests/test_file_service_pagination.py`**

```python
async def test_image_list_has_next_true_when_more_pages(session):
    # seed 3 images, query page=1 page_size=2 → has_next is True

async def test_image_list_has_next_false_on_last_page(session):
    # seed 3 images, query page=2 page_size=2 → has_next is False

async def test_document_list_has_next_empty(session):
    # seed 0, query page=1 page_size=10 → has_next is False, total == 0
```

（fixture 沿用 `tests/conftest.py` 的 `session`；直接调 service，不走 HTTP。）

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_file_service_pagination.py -v`
Expected: FAIL（`has_next` 恒 `False` / 返回类型不含 `ImageOut`）

- [ ] **Step 3: 实现 service 组装**

`list_paginated` 内：

```python
items, total = await self.crud.list_paginated(page, page_size)
return PageResponse(
    data=[ImageOut.model_validate(i) for i in items],  # Document 同理
    total=total,
    page=page,
    page_size=page_size,
    has_next=page * page_size < total,
)
```

- [ ] **Step 4: 修 `ImageService.remove_by_slug` 的预览图孤儿文件**

现状：只有 `path.isfile(raw_file_path)` 为真时才删预览图，raw 缺失时预览图泄漏。改为两个文件各自独立判断删除。

- [ ] **Step 5: 运行测试确认通过**

Run: `uv run pytest tests/test_file_service_pagination.py -v && uv run pytest`
Expected: 新测试 PASS，全量 PASS

- [ ] **Step 6: Commit**

```bash
git add app/service tests/test_file_service_pagination.py
git commit -m "fix(service): compute has_next for pagination and clean preview orphans"
```

---

### Task 6: router 层清理

**Files:**
- Modify: `app/routers/base.py`、`app/routers/auth.py`、`app/routers/image.py`、`app/routers/document.py`、`app/routers/article.py`、`app/routers/category.py`

**Interfaces:**
- Consumes: `CategoryService.get_tree()`（本 task 新增）、`UserService.get_all()`、`UserService.get_by_username()`（本 task 新增）、Task 5 的 `list_paginated`、Task 1 的 `UploadResult`
- Produces: 路由函数名唯一：`upload_image` / `upload_document`（替代两处 `create_upload_file`）；`GET /base/` 有 `response_model`。

- [ ] **Step 1: service 补两个方法**

- `CategoryService.get_tree() -> list[CategoryTree]`：转调 `self.crud.get_tree_all()`。
- `UserService.get_by_username(username: str) -> User | None`：转调 `self.crud.get_by_username`。

- [ ] **Step 2: `routers/base.py` 走 service，补 `response_model`**

新建 `app/schema/common.py` 中的 `BaseInfoOut`（或放 `schema/user.py`，实现者自选一处，与既有 schema 文件职责相符）：`category: list[CategoryTree]`、`user: list[UserOut]`。路由改为调 `CategoryService.get_tree()` + `UserService.get_all()`，返回 `BaseInfoOut`。保持响应 JSON 键名 `category` / `user` 不变。

- [ ] **Step 3: `routers/auth.py` 走 service**

`login` 改用 `UserService(session).get_by_username(data.username)`，不再直接 `UserCrud`。

- [ ] **Step 4: `routers/image.py` / `routers/document.py` 对齐**

- 函数改名 `upload_image` / `upload_document`。
- 上传响应 `response_model=UploadResult`（去掉手写 dict）。
- 列表 `response_model=PageResponse[ImageOut]` / `PageResponse[DocumentOut]`。
- `routers/image.py` 里的 `TypeName` 枚举移到 `routers/image.py` 顶部（紧挨 import），参数 `_t` 改名 `type`（`Query` alias 避免与内建冲突，如 `file_type`）；`get_image` 里补 `else: raise HTTPException(404...)` 兜底，避免未绑定局部变量。

- [ ] **Step 5: 全量测试 + ruff + pyright**

Run: `uv run pytest && uv run ruff check . && uv run pyright`
Expected: 测试全绿；ruff 无新增告警；pyright 无新增错误

- [ ] **Step 6: Commit**

```bash
git add app
git commit -m "refactor(routers): route through services and uniqueify operation names"
```

---

### Task 7: 补关键注释

**Files:**
- Modify: `app/database.py`、`app/model/category.py`、`app/dao/category.py`、`app/dao/article.py`、`app/schema/article.py`、`app/settings.py`

**Interfaces:** 无（纯注释）

- [ ] **Step 1: 在下列位置补中文注释（只写 WHY）**

| 位置 | 注释要点 |
|---|---|
| `database.py:get_session` | 请求成功自动 commit / 异常 rollback；DAO 只 flush 的约定 |
| `model/category.py` | name/slug 部分唯一索引（仅活跃行，软删后可复用）；`path`/`level` 语义 |
| `dao/category.py:_move` | 移动时同步改后代 path/level 的原因 |
| `dao/category.py:soft_delete` | 级联软删子树是为了树接口与平铺接口一致 |
| `dao/article.py:NULLABLE_FIELDS` | null 语义：可空字段显式 null=清空，非空字段 null=400 |
| `dao/article.py:_with_relations` | `with_loader_criteria` 只影响查询加载、不改写关联 |
| `schema/article.py:ArticleUpdate` | 与 NULLABLE_FIELDS 对应的 null 语义说明 |
| `settings.py` | `UploadDir` / `AllowType` 各自用途一行 |

- [ ] **Step 2: 确认没有新增「叙述型」注释**

自查：每个新注释都能回答「不写会让人误解什么吗」。不能就删掉。

- [ ] **Step 3: 全量测试**

Run: `uv run pytest`
Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add app
git commit -m "docs: add WHY comments for soft-delete, path/level, null semantics"
```

---

### Task 8: 同步 README / AGENTS.md / pyproject

**Files:**
- Modify: `README.md`、`AGENTS.md`、`pyproject.toml`

**Interfaces:** 无

- [ ] **Step 1: `pyproject.toml`**

`description` 改为：`FastAPI + SQLModel 异步内容 API（分类 / 文章 / 媒体上传 / JWT 鉴权）`。

- [ ] **Step 2: 更新 `AGENTS.md`**

- 「命令」段加：`uv run ruff check .`、`uv run pyright`。
- 删除「无 lint / typecheck / formatter 配置」表述，改为：ruff（`[tool.ruff.lint]`）+ pyright（`[tool.pyright]`，basic）已在 dev 组；无 formatter、无 CI、无 pre-commit。
- 「架构」段：schema 改为 `app/schema/` 包描述；删掉「image/document 被注释未挂载」，改为「image/document 已挂载，上传保持匿名（前端依赖），文章/分类写操作需 Bearer」。
- 补一条：「DAO 不返回 schema；`PageResponse` 组装在 service。例外：`CategoryCrud.get_tree_all` 返回 `CategoryTree`」。
- 测试段补一句：image/document 分页有 service 级测试（`tests/test_file_service_pagination.py`）。

- [ ] **Step 3: 更新 `README.md`**

- 结构树改为 `schema/` 包、`model/category.py`、无 `utils/file.py`/`logger.py`。
- 「开发说明」去掉重复的软删除条目（现有两行几乎相同）。
- 新增「媒体模块」章节：`/image`、`/document` 的列表/上传/下载接口表、上传请求（multipart）、`UploadResult` 响应、**匿名上传**说明、分页参数与 `has_next` 说明。
- 「测试」段补 `tests/test_file_service_pagination.py`。
- 新增「代码检查」段：`uv run ruff check .` / `uv run pyright`。

- [ ] **Step 4: 逐条执行文档里的命令验证**

Run: `uv sync && uv run pytest && uv run ruff check . && uv run pyright`
Expected: 命令存在且可运行（允许 pyright 既有告警，但不得有新增错误）；文档结构树与 `find app -type f` 一致。

- [ ] **Step 5: Commit**

```bash
git add README.md AGENTS.md pyproject.toml
git commit -m "docs: sync README and AGENTS.md with restructured codebase"
```

---

## 执行顺序

Task 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8。每个 task 独立可测、独立 commit；中途停在任一 task 时仓库仍是可运行状态。
