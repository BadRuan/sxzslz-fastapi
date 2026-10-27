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

分层调用：`routers → service → dao → model`，请求/响应模型集中在 `app/schema.py`。

- 入口：`main.py` 的 `app`；`lifespan` 每次启动自动执行一次 `init_db()` 建表（`SQLModel.metadata.create_all`）。
- 路由统一在 `app/routers/__init__.py` 导出为 `*_router`，由 `main.py` 挂载（image / document 也已挂载）。
- 数据库：生产 PostgreSQL + asyncpg；`DATABASE_URL` 等来自 `.env`（`app/settings.py`，pydantic-settings）。
- 会话依赖 `get_session`：请求成功结束时 **自动 commit**，异常 rollback。DAO 层只 `flush`，不要自行 commit。
- 文章一律用 **slug** 定位（UUID 自动生成），没有按 id 的读写接口。
- 分类为**严格二级**：`parent_id=0` 是一级分类（仅展示分组），否则为二级分类（挂文章）；不可建三级。
- 文章只能关联**二级分类**（可同时多个）；文章查询按二级分类 id **精确匹配**，不聚合一级分类下的子分类。
- 分类排序用 `sort`（越小越靠前，同级之间），PATCH 可调；列表/树按 `sort, id` 升序。
- 文章只有一个可见性字段 `is_deleted`（无 `is_hidden`）：`DELETE` 软删除进回收站，列表默认过滤已删文章，后台用 `GET /articles/?is_deleted=true` 枚举回收站、`POST /articles/{slug}/restore` 恢复（需登录，幂等）。分类**硬删除**，删一级分类会**级联删除子分类**并清理 `article_category` 关联（业务层外键，无数据库外键）。
- 批量分类：`POST /articles/batch-category`（需登录）`{slugs[], category_id, mode: add|remove}`，只作用于未删除文章，幂等；任一 slug 不存在/无效分类 → 400 整批不生效（直接操作 `article_category` 关联表）。
- `view_count` 在公开详情 `GET /articles/{slug}` 成功访问时原子 +1（已删文章 404 且不计数）；`like_count` 走 `POST /articles/{slug}/like`。图片/文件**上传**需登录（读接口公开），`user_id` 取当前登录用户（业务层关联，无 DB 外键；**必填无默认**，存量迁移已用 `scripts/migrate_add_user_id.py` 对部署库执行——加列、存量置 1、SET NOT NULL，脚本幂等，其他环境跑同一脚本）。
- 文章作者取当前登录用户（`POST /articles/` 从 JWT 解析）；`settings.DEFAULT_USER_ID` 仅作 service 层不传 `user_id` 时的兜底。`GET /articles/` 支持 `user_id` 过滤（后台展示登录账户文章）。
- 上传落盘 `./uploads/`（`app/settings.py` 的 `upload_dir`）。
- 业务校验错误：dao/service 抛 `ServiceError`（`ValueError` 子类，`app/errors.py`）→ 全局 handler 转 400 `{"detail": "..."}`（路由层不 try/except）；资源不存在 → 404；参数格式非法 → 422。
- ArticleUpdate 的 null 语义：可空字段显式 `null` 表示清空；非空字段传 `null` 返回 400。

## 鉴权

JWT Bearer（`pyjwt`，HS256，密钥 `settings.SECRET_KEY`）。

- `POST /auth/login` → `{"access_token", "token_type": "bearer"}`；`GET /auth/me` 返回当前用户；`PUT /auth/password` 改密（body `{old_password, new_password}`，需登录；旧密码错 → ServiceError 400，新密码 <6 位 → 422）。
- **读接口公开；写操作（分类/文章的 POST/PATCH/DELETE）需 `Authorization: Bearer <token>`**，否则 401。
- 校验逻辑在 `app/auth.py:get_current_user`；测试用 `auth_headers` fixture（`tests/conftest.py`）。
- 无注册接口，用户通过 `User.create_user`（Argon2）入库；测试里的 `default_user` 密码是 `test123`。

## 数据库建表

- 表结构由 SQLModel 模型定义；`main.py` 的 lifespan 每次启动调用一次 `app/database.py:init_db()`，执行 `SQLModel.metadata.create_all` 自动建表（幂等，已存在的表跳过）。
- `init_db()` 内部 `from app import model` 以注册全部模型——缺了这行 `create_all` 会建不出任何表。新增模型放进 `app/model/` 并在 `app/model/__init__.py` 导出即可。
- `create_all` **不会修改已有表结构**：改字段后需对存量库手动执行 DDL，或清库重建。
- `category.name` **允许重名**（无 DB 唯一约束、无应用层查重；不同父级下同名常见。注意：前端按名称匹配分类的配置取首个匹配，重名可能歧义）；分类硬删除后 name 可复用。分类表无 `slug` / `is_deleted` / `path` / `level` 字段。
- 表间关联不使用数据库级外键，仅业务层关联（`article_category` 关联表）。
- 测试：`tests/conftest.py` 用 `SQLModel.metadata.create_all`（SQLite）；`tests/test_init_db.py` 覆盖「启动自动执行一次」「建出全部表」「重复执行幂等」「无数据库外键」。

## 测试

- `pyproject.toml`：`asyncio_mode = "auto"`、`pythonpath = ["."]` — 测试函数直接写 `async def`，不用装饰器。
- `tests/conftest.py`：内存 `sqlite+aiosqlite://` + `StaticPool`；`client` fixture 用 `httpx.ASGITransport` 走真实路由，并 `dependency_overrides[get_session]` 复用测试 session。
- 新模型必须能被 `SQLModel.metadata.create_all` 在 SQLite 上建表；Postgres 专有类型/约束在测试中不会暴露问题。
- API 层测试覆盖文章与认证；分类只有 dao/service 测试。

## 环境变量

`.env`（已 gitignore）：`DATABASE_URL`、`DB_ECHO`、`DEBUG`、`SECRET_KEY`、`DEFAULT_USER_ID`、`CORS_ORIGINS`（逗号分隔）、`ACCESS_TOKEN_EXPIRE_MINUTES`。README 有模板。

## 部署

Docker：`Dockerfile` 用 `pip install -r requirements.txt`，`CMD ["python", "main.py"]` 监听 **0.0.0.0:8088**（不是 fastapi dev 的 8000）。`uploads/` 为 volume。已有 `.dockerignore`（排除 `.env` / `.venv` / `uploads` 等）——镜像内用运行时环境变量注入配置，勿把 `.env` 打进镜像。
