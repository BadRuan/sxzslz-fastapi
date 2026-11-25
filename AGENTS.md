# AGENTS.md

FastAPI + SQLModel 异步内容 API（分类 / 文章 / JWT 鉴权）。小型单包项目，无 monorepo。

## 命令

```bash
uv sync                      # 安装依赖（含 dev 组：pytest / pytest-asyncio / aiosqlite）
uv run fastapi dev           # 开发服务，入口 main:app（pyproject [tool.fastapi]），默认 127.0.0.1:8000
uv run pytest                # 全部测试（内存 SQLite，无需外部服务）
uv run pytest tests/test_article_api.py::test_name   # 单测
```

- Python 3.12（`.python-version`）。包管理用 **uv**；`pyproject.toml` + `uv.lock` 是依赖真相源。
- `requirements.txt` 是给 Docker（pip）用的**钉死版本快照**，改动依赖后需 `uv export --no-dev --no-hashes -o requirements.txt` 同步，勿手改。
- **无 lint / typecheck / formatter 配置**（无 ruff、mypy、black）。不要假称跑过，也不要擅自引入。
- 无 CI、无 pre-commit。

## 架构

分层调用：`routers → service → dao → model`，请求/响应模型集中在 `app/schema/`（包，不是单文件）；横切能力集中在 `app/core/`：`auth.py`（JWT）、`database.py`（engine/`get_session`/`init_db`）、`error.py`（`ServiceError` + 全局 handler）。`app/auth.py`、`app/database.py`、`app/errors.py` 是**兼容层**（重导出，旧导入路径继续可用），新代码直接导入 `app.core.*`；`app/database.py:init_db` 使用本模块 `engine`，便于测试 `monkeypatch.setattr(app.database, "engine", ...)` 注入。跨层共享的 403 文案与分页阈值在 `app/types.py`（`CATEGORY_MANAGE_FORBIDDEN` 等），图片/文档路由共用辅助在 `app/routers/_common.py`（`visible_user_id` / `ensure_owner_or_superuser` / `to_upload_result_*`）。

- 入口：`main.py` 的 `app`；`lifespan` 每次启动自动执行一次 `init_db()` 建表（`SQLModel.metadata.create_all`）。
- 路由统一在 `app/routers/__init__.py` 导出为 `*_router`，由 `main.py` 挂载（image / document 也已挂载）。
- 数据库：生产 PostgreSQL + asyncpg；`DATABASE_URL` 等来自 `.env`（`app/settings.py`，pydantic-settings）。
- 会话依赖 `get_session`：请求成功结束时 **自动 commit**，异常 rollback。DAO 层只 `flush`，不要自行 commit。
- 文章一律用 **slug** 定位（UUID 自动生成），没有按 id 的读写接口。
- 分类为**严格二级**：`parent_id=0` 是一级分类（仅展示分组），否则为二级分类（挂文章）；不可建三级。
- 文章只能关联**二级分类**（可同时多个）；文章查询按二级分类 id **精确匹配**，不聚合一级分类下的子分类。
- 分类排序用 `sort`（越小越靠前，同级之间），PATCH 可调；列表/树按 `sort, id` 升序。
- 文章只有一个可见性字段 `is_deleted`（无 `is_hidden`）：`DELETE` 软删除进回收站，列表默认过滤已删文章，后台用 `GET /articles/?is_deleted=true` 枚举回收站、`POST /articles/{slug}/restore` 恢复（需登录，幂等）。分类**硬删除**，删一级分类会**级联删除子分类**并清理 `article_category` 关联（业务层外键，无数据库外键）。
- 批量分类：`POST /articles/batch-category`（仅超管）`{slugs[], category_id, mode: add|remove}`，只作用于未删除文章，幂等；任一 slug 不存在/无效分类 → 400 整批不生效（直接操作 `article_category` 关联表）。
- `view_count` 在公开详情 `GET /articles/{slug}` 成功访问时原子 +1（已删文章 404 且不计数）；`like_count` 走 `POST /articles/{slug}/like`。图片/文件**上传**需登录（读接口公开），`user_id` 取当前登录用户（业务层关联，无 DB 外键；**必填无默认**，存量迁移已用 `scripts/migrate_add_user_id.py` 对部署库执行——加列、存量置 1、SET NOT NULL，脚本幂等，其他环境跑同一脚本）。
- **角色权限**：`user.is_superuser` 标识超管（默认账号 `ruanfumin`；存量用 `scripts/migrate_add_is_superuser.py` 迁移）。超管可创建/改/删/恢复任意文章，并可在 create/PATCH 指定 `user_id`（作者）与 `create_at`（发布时间）；普通用户仅能操作**自己**的文章，`user_id`/`create_at` 在 PATCH 中被剥离，`view_count`/`like_count` 不开放 PATCH。`GET /articles/` 按调用者收敛可见范围：匿名=公开全量（前台）；普通用户=固定只看**自己**的文章（`user_id` 参数被忽略，`is_deleted=true` 回收站同理）；超管=全量可过滤；带非法/过期 token → 401 不静默降级为匿名。分类写操作（POST/PATCH/DELETE `/categories/`）与 `POST /articles/batch-category` **仅超管**，普通用户 → 403 `仅超级管理员可管理文章分类`；分类 `GET` 保持公开。用户账户管理（`POST /users/`、`POST /users/{id}/reset-password`、`DELETE /users/{id}`）**仅超管**：创建普通账户（密码缺省 `settings.DEFAULT_USER_PASSWORD`=abc123）、重置普通账户密码为 abc123、删除普通账户；超级管理员账户受保护（403 `不能删除超级管理员账户` / `不能重置超级管理员密码`）。删除账户用 Core `DELETE` 用户行（绕过 ORM 关系级联），其文章/图片/文档保留、`user` 关联自然为 null。图片/文档列表需登录：超管见全部、普通只见自己；文档下载限本人/超管；图片本体 `GET /image/{slug}` 保持公开（封面依赖）。图片新增 `PATCH`（改名）/`DELETE`（删记录+原图+预览）；文档改名/删除超管可操作他人文件。
- 文章作者默认取当前登录用户（`POST /articles/` 从 JWT 解析）；body 可选传 `user_id`（≥1）指定发布主体**（仅超管，普通用户传他人 → 403）**。`settings.DEFAULT_USER_ID` 仅作 service 层不传 `user_id` 时的兜底。`GET /articles/` 支持 `user_id` 过滤（仅超管生效，普通用户被强制收敛为本人）与 `keyword` 标题模糊搜索（多词空格分隔 AND、仅匹配标题、大小写不敏感、`%`/`_` 转义为字面量，可见范围内生效——超管搜全量、普通用户只搜自己，回收站 `is_deleted=true` 同样可用；纯空白/超 50 字 → 422）。后台管理即：`GET /articles/?keyword=` 搜标题定位 → `PATCH /articles/{slug}` 编辑。
- 无限滚动：`GET /articles/infinite` 游标翻页，可见范围与 `GET /articles/` 完全一致（匿名全量/普通只看自己/超管可过滤）；响应 `ArticleInfiniteOut{data, limit, has_more, next_cursor}`，`limit` 1~100 默认 20，支持与列表同套的 `category_id`/`user_id`/`is_deleted`/`keyword`/`sort` 过滤。游标是不透明串（`(排序字段, id)` 双键倒序定位，同发布时间不重不漏），篡改或非本接口签发 → 400 `无效的游标`；`GET /articles/` 的 `page` 分页契约不受影响（两套接口）。
- 操作日志审计：文章/图片/文档/用户的写操作（含失败）经 `OperationService.log_operation` 落 `operation_log` 表（模型 `app/model/operation_log.py`；router 层经 `app/routers/_common.py:client_info` 传 operator/ip/ua）；日志写失败仅记 Python 日志 `sxzslz.operation` 不影响主业务。**已知取舍：日志随主请求事务提交，主请求整体回滚时该请求的失败日志也会丢**（未来可改独立会话）。查询 `GET /logs/` **仅超管**（403 `仅超级管理员可查看操作日志`）：分页 + `action`/`object_type`/`result`/`operator_id` 过滤，`created_at desc, id desc`。
- 上传落盘 `./uploads/`（`app/settings.py` 的 `upload_dir`）。上传为**分块流式落盘**（`write_upload_stream`，1MB/块，避免整文件进内存）；大小上限 `settings.MAX_IMAGE_SIZE_MB`（默认 10）/ `MAX_DOCUMENT_SIZE_MB`（默认 50），超限或空文件 → ServiceError 400 并清理半成品。落盘 `OSError` 由 `storage_error_from` 归类为 `StorageError`（ENOSPC=磁盘满 / EACCES·EPERM=无写权限 / 其他=保存失败）→ service 转 ServiceError 400；客户端中断（`ClientDisconnect`，前端 `AbortController` 取消）与任何未预期异常同样清理半成品。MIME 白名单在 `settings.allow_type`（图片：JPEG/PNG/GIF/WebP/BMP/TIFF/ICO；文档：txt/csv/md/rtf/pdf/Office 全家桶/ODF/zip·7z·rar·gz·tar/epub），友好后缀串 `IMAGE_TYPE_LABEL` / `DOCUMENT_TYPE_LABEL`。进度条由前端 `XMLHttpRequest.upload.onprogress` + `AbortController` 实现（`docs/frontend-api.md` 的 `uploadWithProgress`，图片/文档共用）。`UploadResult` 含 `size_bytes` / `url`（图片=预览、文档=下载）/ `raw_url`（仅图片）。批量上传端点 `POST /image/batch/`、`POST /document/batch/`（表单字段 `files`，上限 `settings.MAX_BATCH_FILES` 默认 20，整批原子：任一文件失败 400 并清理本批已落盘文件，DB 记录随请求事务回滚）。
- 文档管理：`PATCH /document/{slug}` 仅上传者或超管可改展示名 `raw_filename`（slug/内容不变）；`DELETE /document/{slug}` 仅上传者或超管可删（DB + 磁盘文件一并清理，硬删不可恢复）。非本人且非超管 → 403 `无权限操作该文件`，不存在 → 404。图片同样有 PATCH 改名 / DELETE；图片本体读取保持公开。
- 业务校验错误：dao/service 抛 `ServiceError`（`ValueError` 子类，实现在 `app/core/error.py`，`app/errors.py` 兼容重导出）→ 全局 handler 转 400 `{"detail": "..."}`（路由层不 try/except）；资源不存在 → 404；参数格式非法 → 422。
- ArticleUpdate 的 null 语义：可空字段显式 `null` 表示清空；非空字段传 `null` 返回 400。

## 鉴权

JWT Bearer（`pyjwt`，HS256，密钥 `settings.SECRET_KEY`）。

- `POST /auth/login` → `{"access_token", "token_type": "bearer"}`；`GET /auth/me` 返回当前用户；`PUT /auth/password` 改密（body `{old_password, new_password}`，需登录；旧密码错 → ServiceError 400，新密码 <6 位 → 422）。
- **读接口公开；写操作（分类/文章的 POST/PATCH/DELETE）需 `Authorization: Bearer <token>`**，否则 401；分类写操作、批量分类与用户账户管理额外要求超管（普通用户 → 403）。
- 校验逻辑在 `app/core/auth.py`（`app/auth.py` 兼容重导出）：`get_current_user`（必须登录）、`get_optional_user`（可选登录，供 `GET /articles/` 可见范围收敛）、`require_superuser(detail)` 依赖工厂（仅超管，403）；测试用 `auth_headers` fixture（`tests/conftest.py`）。
- 无注册接口，用户通过 `User.create_user`（Argon2）入库；测试里的 `default_user` 密码是 `test123`。

## 数据库建表

- 表结构由 SQLModel 模型定义；`main.py` 的 lifespan 每次启动调用一次 `app/database.py:init_db()`，执行 `SQLModel.metadata.create_all` 自动建表（幂等，已存在的表跳过）。
- 模型注册发生在 `app/core/database.py` 顶部的 `from app import model`（`app/database.py:init_db` 经导入链同样生效）——缺了这行 `create_all` 会建不出任何表。新增模型放进 `app/model/` 并在 `app/model/__init__.py` 导出即可。
- `create_all` **不会修改已有表结构**：改字段后需对存量库手动执行 DDL，或清库重建。
- `category.name` **允许重名**（无 DB 唯一约束、无应用层查重；不同父级下同名常见。注意：前端按名称匹配分类的配置取首个匹配，重名可能歧义）；分类硬删除后 name 可复用。分类表无 `slug` / `is_deleted` / `path` / `level` 字段。
- 表间关联不使用数据库级外键，仅业务层关联（`article_category` 关联表）。
- 测试：`tests/conftest.py` 用 `SQLModel.metadata.create_all`（SQLite）；`tests/test_init_db.py` 覆盖「启动自动执行一次」「建出全部表」「重复执行幂等」「无数据库外键」。

## 测试

- `pyproject.toml`：`asyncio_mode = "auto"`、`pythonpath = ["."]` — 测试函数直接写 `async def`，不用装饰器。
- `tests/conftest.py`：内存 `sqlite+aiosqlite://` + `StaticPool`；`client` fixture 用 `httpx.ASGITransport` 走真实路由，并 `dependency_overrides[get_session]` 复用测试 session。
- 新模型必须能被 `SQLModel.metadata.create_all` 在 SQLite 上建表；Postgres 专有类型/约束在测试中不会暴露问题。
- API 层测试覆盖文章、认证、分类（`tests/test_category_api.py`）、`/base`（`tests/test_base_api.py`）与操作日志（`tests/test_operation_log_api.py`）。

## 环境变量

`.env`（已 gitignore）：`DATABASE_URL`、`DB_ECHO`、`DEBUG`、`SECRET_KEY`、`DEFAULT_USER_ID`、`CORS_ORIGINS`（逗号分隔）、`ACCESS_TOKEN_EXPIRE_MINUTES`、`MAX_IMAGE_SIZE_MB`、`MAX_DOCUMENT_SIZE_MB`。README 有模板。

## 部署

Docker：`Dockerfile` 用 `pip install -r requirements.txt`，`CMD ["python", "main.py"]` 监听 **0.0.0.0:8088**（不是 fastapi dev 的 8000）。`uploads/` 为 volume。已有 `.dockerignore`（排除 `.env` / `.venv` / `uploads` 等）——镜像内用运行时环境变量注入配置，勿把 `.env` 打进镜像。
