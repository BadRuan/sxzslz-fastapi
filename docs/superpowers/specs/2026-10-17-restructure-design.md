# sxzslz-fastapi 深度梳理设计

日期：2026-10-17
状态：已批准（image/document 保持匿名上传）

## 意图

现有代码分层（routers → service → dao → model）方向正确，但模块划分粗糙、层间职责有越界、命名不统一、存在死代码与文档漂移。本次把模块划分与层间边界一起理顺，补齐关键注释，并同步 README / AGENTS.md，使项目符合常见 FastAPI 项目最佳实践。

## 目标

1. **模块划分清晰**：schema 按领域拆包；Category 模型独立成文件；utils 只保留真正被使用的代码。
2. **层间边界干净**：router 不直接摸 DAO；DAO 返回 ORM 模型，service 负责转 schema；密码哈希器单一实例。
3. **命名与约定统一**：PEP8 类名、slug 生成函数命名对齐、上传目录/白名单命名可读。
4. **修掉已知缺陷**：image/document 分页 `has_next` 写死、`suffiex` 拼写、image 删除预览图逻辑、路由函数重名。
5. **注释只写非显然的 WHY**：不堆「这行是干什么的」，只标注并发/软删/层级路径等有隐含约束的地方。
6. **文档与代码一致**：README 补 image/document 接口与当前结构；AGENTS.md 修正 lint/typecheck、路由挂载状态等过时描述。

## 非目标

- 不改数据库表结构 / 不写新迁移（本次不动模型字段）。
- 不引入新依赖、不加 CI、不加 pre-commit。
- 不做异步文件 IO 改造（上传仍是同步 `open`，ruff 已 ignore ASYNC230）。
- 不重构测试文件布局（测试按层组织已经合理）。
- 不做性能优化。

## 约束

- Python 3.12 + uv + FastAPI + SQLModel；现有 `uv run pytest` 必须全绿。
- 依赖真相源是 `pyproject.toml` / `uv.lock`；本次不动依赖，`requirements.txt` 无需重导。
- Alembic 迁移不变；老库 `stamp head` 流程不变。
- 保持对外 API 路径与响应结构不变（见下方「行为变化」例外）。

## 目标结构

```
app/
├── auth.py               # JWT 签发/校验 + get_current_user
├── database.py           # engine / get_session / init_db
├── settings.py           # Settings + UploadDir + AllowType
├── schema/               # 请求/响应模型，按领域拆分
│   ├── __init__.py       # 聚合导出（保持 from app.schema import X 兼容）
│   ├── common.py         # PageResponse
│   ├── auth.py           # LoginRequest / TokenOut
│   ├── user.py           # UserOut
│   ├── category.py       # CategoryTree / CategoryOut / Create / Update
│   ├── article.py        # ArticleOut / ArticleDetailOut / Create / Update
│   └── file.py           # ImageOut / DocumentOut / UploadResult
├── model/
│   ├── article.py        # Article / ArticleCategory
│   ├── category.py       # Category（从 article.py 移出）
│   ├── user.py           # User（含唯一 PasswordHasher）
│   ├── image.py          # Image
│   └── document.py       # Document
├── dao/                  # 只返回 ORM 模型或 (list, total)；不 import schema
├── service/              # 业务校验 + 转 schema；统一抛 ValueError
├── routers/              # 只做参数解析、鉴权、异常转 HTTP
└── utils/
    └── genwebp.py        # 仅保留被使用的 WebP 生成
main.py
```

## 关键决策

### 1. schema 拆包，`app/schema/__init__.py` 聚合导出

对外仍是 `from app.schema import ArticleCreate` 这类写法，import 路径不断。内部按 domain 分文件，方便定位与扩展。

### 2. Category 模型独立为 `model/category.py`

Category 是核心领域实体，和 Article 同级。`ArticleCategory` 多对多表留在 `model/article.py`（它描述的是文章侧的关联）。`model/__init__.py` 导出不变。

### 3. DAO 不再返回 schema

现状违规点：
- `dao/image.py` / `dao/document.py` 的 `list_paginated` 直接返回 `PageResponse[Image]`
- `dao/user.py:get_by_id` 返回 `UserOut`

改为 DAO 返回 `list[Model]` + `total`（或 `Model | None`），service 层组装 `PageResponse` / `UserOut`。分页的 `has_next` 计算统一收口到 service（`page * page_size < total`）。

### 4. 密码哈希器收口到 model/user.py

`dao/user.py` 与 `model/user.py` 各 new 了一个 `PasswordHasher`。`User.create_user` / `check_password` 已经封装了哈希逻辑，dao 删掉自己的实例，登录校验走 `user.check_password`（现状 router 已是如此）。

### 5. router 层去掉对 DAO 的直接依赖

- `routers/base.py`：改用 `CategoryService.get_tree()` + `UserService.get_all()`，不再直接 `CategoryCrud.get_tree_all()`。
- `routers/auth.py`：登录查询改走 `UserService.get_by_username()`。
- 响应补上 `response_model`（base 接口目前裸 dict）。

### 6. image / document 与核心模块对齐

| 项 | 现状 | 改为 |
|---|---|---|
| 写操作鉴权 | 无 | **保持匿名上传**（用户决定，前端依赖匿名上传） |
| `has_next` | 写死 `False` | `page * page_size < total` |
| DAO 返回 | `PageResponse[Image]` | `(list[Image], total)` |
| 列表响应 | `response_model=PageResponse`（无参） | `PageResponse[ImageOut]` / `PageResponse[DocumentOut]` |
| 路由函数名 | 两处都叫 `create_upload_file` | `upload_image` / `upload_document` |
| 删除策略 | 硬删 | **保持硬删**（文件资源与文章内容的生命周期不同，不强行统一软删） |

### 7. 命名与死代码

- `IMAGE_DIR` → `UploadDir`，`ALLOW_TYPE` → `AllowType`，`Dist_Dir` → 删除（直接返回路径字符串）。
- `gen_slug` / `generate_slug` 统一为模块级 `generate_slug()`，长度差异保留（article 16、user 12、file 32 hex），各自文件内定义。
- 删除从未被引用的 `utils/file.py:generate_unique_filename` 与 `utils/logger.py:Logger`（若日后需要日志再引入）。
- 删除无调用方的 DAO 方法：`UserCrud.get_by_id` / `get_count`、`ImageCrud.get_count` / `get_view`、`DocumentCrud.get_count` / `get_download`、`CategoryCrud.get_by_id`。
- `DocumentCrud.get_view`（实为浏览量 +1）改名 `record_view`，与 `ImageCrud` 对齐。
- `suffiex` → `suffix`。
- 删除 `schema.py` 里未使用的 `T = TypeVar("T")`。

### 8. 注释策略

只在以下位置写注释（中文，与现状一致）：
- 软删除 / 部分唯一索引的隐含语义
- 分类 `path`/`level` 层级路径的维护规则（创建/移动/级联删除）
- ArticleUpdate 的 null 语义（清空 vs 拒绝）
- `get_session` 自动 commit / DAO 只 flush 的约定
- 并发插入 IntegrityError → 400 的处理意图

不为显而易见的赋值、import、简单函数加注释。

## 行为变化（需知晓）

1. image/document 列表的 `has_next` 从恒 `false` 变为真实值。
2. image/document **保持匿名上传**（用户确认前端依赖此行为），仅核心模块写操作需 Bearer。
3. 以上之外，路由路径、请求体、响应体结构均不变。

## 文档更新

- **README.md**：修正「开发说明」重复条目；补 image/document 接口表与请求/响应示例；更新项目结构树；补 ruff/pyright 命令；`pyproject.toml` 的 `description` 同步为真实描述。
- **AGENTS.md**：修正「无 lint/typecheck」→ 已有 ruff + pyright（dev 组）；修正「image/document 注释未挂载」→ 已挂载、上传保持匿名；补 schema 包结构与 DAO 不返回 schema 的约定；补 `uv run ruff check` / `uv run pyright` 命令。

## 验收

1. `uv run pytest` 全绿。
2. `uv run ruff check` 无新增告警（既有 ignore 规则保持）。
3. `uv run pyright` 无新增错误。
4. README / AGENTS.md 中的命令逐条可执行，结构树与真实目录一致。
5. 现有测试不改断言（除因 `has_next` 修正而必要的调整——目前测试未覆盖 image/document 分页）。
