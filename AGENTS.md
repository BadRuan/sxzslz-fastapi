# AGENTS.md

FastAPI + SQLModel 异步内容 API（分类 / 文章 / JWT 鉴权）。小型单包项目，无 monorepo。

## 命令

```bash
uv sync                      # 安装依赖（含 dev 组：pytest / pytest-asyncio / aiosqlite）
uv run fastapi dev           # 开发服务，入口 main:app（pyproject [tool.fastapi]），默认 127.0.0.1:8000
uv run pytest                # 全部测试（内存 SQLite，无需外部服务）
uv run pytest tests/test_article_api.py::test_name   # 单测
uv run alembic upgrade head  # 手动执行数据库迁移
uv run alembic revision --autogenerate -m "msg"      # 生成迁移（改模型后）
```

- Python 3.12（`.python-version`）。包管理用 **uv**；`pyproject.toml` + `uv.lock` 是依赖真相源。
- `requirements.txt` 是给 Docker（pip）用的**钉死版本快照**，改动依赖后需 `uv export --no-dev --no-hashes -o requirements.txt` 同步，勿手改。
- **无 lint / typecheck / formatter 配置**（无 ruff、mypy、black）。不要假称跑过，也不要擅自引入。
- 无 CI、无 pre-commit。

## 架构

分层调用：`routers → service → dao → model`，请求/响应模型集中在 `app/schema.py`。

- 入口：`main.py` 的 `app`；`lifespan` 启动时执行 `init_db()` = `alembic upgrade head`。
- 路由统一在 `app/routers/__init__.py` 导出为 `*_router`，由 `main.py` 挂载。
- **image / document 路由已实现但被注释未挂载**（`main.py` 末尾）；改动它们不影响当前 API 表面。
- 数据库：生产 PostgreSQL + asyncpg；`DATABASE_URL` 等来自 `.env`（`app/settings.py`，pydantic-settings）。
- 会话依赖 `get_session`：请求成功结束时 **自动 commit**，异常 rollback。DAO 层只 `flush`，不要自行 commit。
- 文章一律用 **slug** 定位（UUID 自动生成），没有按 id 的读写接口。
- 软删除：`is_deleted`；删除分类会**级联软删整棵子树**。分类层级用 `parent_id` / `path` / `level`，`parent_id=0` 表示顶级。
- 文章作者固定取 `settings.DEFAULT_USER_ID`（默认 1），前端不传作者。
- 上传落盘 `./uploads/`（`app/settings.py` 的 `upload_dir`）。
- 业务校验错误：service 抛 `ValueError` → router 转 400 `{"detail": "..."}`；资源不存在 → 404；参数格式非法 → 422。
- ArticleUpdate 的 null 语义：可空字段显式 `null` 表示清空；非空字段传 `null` 返回 400。

## 鉴权

JWT Bearer（`pyjwt`，HS256，密钥 `settings.SECRET_KEY`）。

- `POST /auth/login` → `{"access_token", "token_type": "bearer"}`；`GET /auth/me` 返回当前用户。
- **读接口公开；写操作（分类/文章的 POST/PATCH/DELETE）需 `Authorization: Bearer <token>`**，否则 401。
- 校验逻辑在 `app/auth.py:get_current_user`；测试用 `auth_headers` fixture（`tests/conftest.py`）。
- 无注册接口，用户通过 `User.create_user`（Argon2）入库；测试里的 `default_user` 密码是 `test123`。

## 数据库迁移（Alembic）

- 迁移在 `alembic/versions/`；`init_db()` 启动时自动 `upgrade head`。
- 改 SQLModel 字段后：`uv run alembic revision --autogenerate -m "..."`，**人工核对**生成的迁移再提交。
- `category.name` / `category.slug` 的唯一性是「仅活跃行」部分唯一索引（`uq_category_name` / `uq_category_slug`），软删后可复用——迁移里勿改成全表唯一。
- **既有老库**（曾用 `create_all` + 幂等 SQL 建表）首次接入 Alembic 需先 `uv run alembic stamp head`，否则 upgrade 会因表已存在而失败。
- 测试不跑 Alembic：`tests/conftest.py` 用 `SQLModel.metadata.create_all`（SQLite）；`tests/test_migrations.py` 单独验证迁移可在干净 SQLite 上建表。

## 测试

- `pyproject.toml`：`asyncio_mode = "auto"`、`pythonpath = ["."]` — 测试函数直接写 `async def`，不用装饰器。
- `tests/conftest.py`：内存 `sqlite+aiosqlite://` + `StaticPool`；`client` fixture 用 `httpx.ASGITransport` 走真实路由，并 `dependency_overrides[get_session]` 复用测试 session。
- 新模型必须能被 `SQLModel.metadata.create_all` 在 SQLite 上建表；Postgres 专有类型/约束在测试中不会暴露问题。
- API 层测试覆盖文章与认证；分类只有 dao/service 测试。

## 环境变量

`.env`（已 gitignore）：`DATABASE_URL`、`DB_ECHO`、`DEBUG`、`SECRET_KEY`、`DEFAULT_USER_ID`、`CORS_ORIGINS`（逗号分隔）、`ACCESS_TOKEN_EXPIRE_MINUTES`。README 有模板。

## 部署

Docker：`Dockerfile` 用 `pip install -r requirements.txt`，`CMD ["python", "main.py"]` 监听 **0.0.0.0:8088**（不是 fastapi dev 的 8000）。`uploads/` 为 volume。已有 `.dockerignore`（排除 `.env` / `.venv` / `uploads` 等）——镜像内用运行时环境变量注入配置，勿把 `.env` 打进镜像。
