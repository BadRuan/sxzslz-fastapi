# sxzslz-fastapi

基于 FastAPI 的异步 Web API 服务，提供分类、文章的增删改查与分页查询能力。

## 技术栈

- **框架**: FastAPI
- **ORM**: SQLModel (基于 SQLAlchemy + Pydantic)
- **数据库**: PostgreSQL
- **异步驱动**: asyncpg
- **包管理**: uv
- **密码哈希**: argon2-cffi
- **测试**: pytest + pytest-asyncio + aiosqlite（内存数据库，无需外部依赖）

## 项目结构

```
sxzslz-fastapi/
├── app/
│   ├── dao/              # 数据访问层（CRUD）
│   │   ├── article.py    #   ArticleCrud
│   │   ├── category.py   #   CategoryCrud
│   │   ├── user.py
│   │   ├── image.py
│   │   └── document.py
│   ├── model/            # 数据模型（SQLModel）
│   │   ├── article.py    #   Article / Category / ArticleCategory
│   │   ├── user.py
│   │   ├── image.py
│   │   └── document.py
│   ├── routers/          # 路由层（API 接口）
│   │   ├── base.py
│   │   ├── category.py
│   │   ├── article.py
│   │   ├── image.py
│   │   └── document.py
│   ├── service/          # 业务逻辑层
│   │   ├── category.py   #   CategoryService
│   │   ├── article.py    #   ArticleService
│   │   ├── user.py
│   │   ├── image.py
│   │   └── document.py
│   ├── utils/            # 工具函数
│   ├── database.py       # 数据库连接与初始化
│   ├── schema.py         # 请求/响应模型（含分页）
│   └── settings.py       # 环境变量配置
├── tests/                # 测试（dao / service / API 层）
│   ├── conftest.py
│   ├── test_category_dao.py
│   ├── test_category_service.py
│   ├── test_article_dao.py
│   ├── test_article_service.py
│   └── test_article_api.py
├── main.py               # 应用入口
├── pyproject.toml        # 项目依赖与配置
└── .env                  # 环境变量（需自行创建）
```

## 快速开始

### 1. 环境准备

- Python 3.12+
- PostgreSQL 数据库
- [uv](https://docs.astral.sh/uv/) 包管理器

### 2. 配置环境变量

创建 `.env` 文件：

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname
DB_ECHO=false
DEBUG=false
SECRET_KEY=your-secret-key-change-in-production
DEFAULT_USER_ID=1
```

> `DEFAULT_USER_ID` 为创建文章时的默认作者 ID，需对应数据库中已存在的用户。

### 3. 安装依赖

```bash
uv sync
```

### 4. 启动服务（开发模式）

```bash
uv run fastapi dev
```

`fastapi dev` 会使用 `pyproject.toml` 中配置的 `[tool.fastapi] entrypoint = "main:app"`，
默认开启热重载，监听 `127.0.0.1:8000`。

如需指定主机与端口：

```bash
uv run fastapi dev --host 0.0.0.0 --port 8088
```

启动后访问：

- API 文档（Swagger UI）: <http://localhost:8000/docs>
- ReDoc 文档: <http://localhost:8000/redoc>

## API 接口

### 基础信息 `/base`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/base/` | 获取分类树与用户列表 |

### 分类模块 `/categories`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/categories/` | 创建分类 |
| GET | `/categories/` | 获取所有分类（扁平列表） |
| GET | `/categories/{id}` | 获取单个分类 |
| PATCH | `/categories/{id}` | 修改分类 |
| DELETE | `/categories/{id}` | 删除分类（软删除，级联软删整棵子树） |

**创建分类请求体**：

```json
{
    "name": "财务信息",
    "slug": "caiwu",
    "parent_id": 0,
    "sort": 0
}
```

- `name` / `slug`：必填，对**未删除**的分类唯一（软删后可被新分类复用）
- `parent_id`：父分类 ID，`0` 表示顶级分类（默认 `0`）
- `sort`：排序值，越小越靠前（默认 `0`）

**修改分类请求体**（所有字段可选，仅更新传入的字段）：

```json
{
    "name": "财务公开",
    "sort": 10
}
```

### 文章模块 `/articles`

> 文章一律以 **slug** 定位（不再支持按 id 查询/修改/删除）。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/articles/` | 创建文章 |
| GET | `/articles/` | 分页获取文章列表 |
| GET | `/articles/{slug}` | 获取文章详情 |
| PATCH | `/articles/{slug}` | 修改文章 |
| DELETE | `/articles/{slug}` | 删除文章（软删除） |

**分页查询参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `page` | int | 1 | 页码，从 1 开始 |
| `page_size` | int | 20 | 每页条数（最大 100） |
| `category_id` | int | 无 | 按分类过滤（可选，含其全部子分类；分类不存在或已删除时返回空列表） |

示例：`GET /articles/?page=2&page_size=10&category_id=3`

**创建文章请求体**：

```json
{
    "title": "文章标题",
    "content": "文章内容",
    "cover_img_slug": "a1b2c3d4",
    "is_hidden": false,
    "is_recommended": true,
    "category_ids": [1, 2]
}
```

- `title`：必填
- `content`、`cover_img_slug`：可选
- `category_ids`：关联分类 ID 列表（文章与分类为多对多关系，默认空列表）
- 作者由服务端默认指定（`DEFAULT_USER_ID`），无需前端传入

**修改文章请求体**（所有字段可选，仅更新传入的字段，`category_ids` 传入时整体替换关联分类）：

```json
{
    "title": "新标题",
    "is_recommended": false,
    "category_ids": [2]
}
```

- 可空字段（`content`、`cover_img_slug`）显式传 `null` 表示清空；`category_ids` 传 `null` 表示清空全部关联分类
- 非空字段（`title`、`is_hidden`、`is_recommended`）传 `null` 返回 400

**分页列表响应**：

```json
{
    "data": [
        {
            "id": 1,
            "slug": "a1b2c3d4e5f6g7h8",
            "cover_img_slug": null,
            "title": "文章标题",
            "is_hidden": false,
            "is_recommended": true,
            "create_at": "2026-10-16T10:00:00",
            "view_count": 0,
            "like_count": 0,
            "categories": [
                {"id": 1, "name": "财务信息", "slug": "caiwu", "path": "/1/", "level": 1, "sort": 0, "children": []}
            ],
            "user": {"id": 1, "slug": "u1u1u1u1u1u1", "nickname": "管理员"}
        }
    ],
    "total": 100,
    "page": 1,
    "page_size": 20,
    "has_next": true
}
```

文章详情（`GET /articles/{slug}`）与创建/修改响应额外包含 `content` 字段。

## 数据模型

### User

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| slug | str | URL 唯一标识（自动生成） |
| username | str | 用户名（唯一） |
| nickname | str | 昵称（唯一） |
| password | str | 密码（Argon2 加密） |

### Category

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| name | str | 分类名称（对未删除分类唯一，部分索引约束） |
| slug | str | URL 唯一标识（对未删除分类唯一，部分索引约束） |
| parent_id | int | 父分类 ID（0 表示顶级） |
| path | str | 层级路径，如 `/1/3/7/` |
| level | int | 层级深度，顶级为 1 |
| sort | int | 排序值，越小越靠前 |
| is_deleted | bool | 软删除标记 |

### Article

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| slug | str | URL 唯一标识（自动生成） |
| cover_img_slug | str | 封面图标识（可选） |
| title | str | 标题 |
| content | str | 内容（可选） |
| user_id | int | 作者 ID |
| is_hidden | bool | 是否隐藏 |
| is_recommended | bool | 是否推荐 |
| view_count | int | 阅读量 |
| like_count | int | 点赞数 |
| is_deleted | bool | 软删除标记 |
| create_at | datetime | 创建时间 |
| categories | list | 关联分类（多对多） |

## 测试

项目使用 pytest，测试运行在内存 SQLite 数据库上（aiosqlite），无需额外的数据库配置。

### 安装测试依赖

```bash
uv sync
```

`uv sync` 会一并安装 `[dependency-groups]` 中的 dev 依赖（pytest、pytest-asyncio、aiosqlite）。

### 运行测试

```bash
uv run pytest
```

查看详细输出：

```bash
uv run pytest -v
```

### 测试说明

- `tests/conftest.py`：使用内存 SQLite + `StaticPool` 提供隔离的测试引擎与 session，并提供 API 层测试客户端（`client`，走真实路由）。
- `tests/test_category_dao.py` / `tests/test_article_dao.py`：数据访问层测试，覆盖创建、查询、更新、移动、软删除（含级联）、分页等。
- `tests/test_category_service.py` / `tests/test_article_service.py`：业务层测试，覆盖唯一性校验（含软删复用与并发冲突）、默认作者、分页响应结构等。
- `tests/test_article_api.py`：API 层测试，验证文章以 slug 定位的路由行为（200/204/404）。

## 开发说明

- 数据库表会在首次启动时自动创建（`init_db`），并通过幂等 SQL 补齐软删除字段；同时将 `category.name` / `category.slug` 的旧有全表唯一约束迁移为「仅活跃行」的部分唯一索引（`uq_category_name` / `uq_category_slug`），软删分类的名称与 slug 可被复用。
- 分类与文章删除均为软删除（`is_deleted = True`），列表与详情查询自动过滤已删除记录。
- 删除分类会**级联软删其整棵子树**，保证分类树接口（`/base/`）与平铺列表接口（`/categories/`）行为一致；已软删的分类不会出现在文章详情的 `categories` 中。
- 分类支持多级层级（通过 `parent_id`、`path`、`level` 维护），移动分类时会同步更新其后代路径。
- 文章通过 **slug** 定位（`GET` / `PATCH` / `DELETE /articles/{slug}`），slug 使用 UUID 自动生成；文章与分类为多对多关系。
- 文章列表按 `category_id` 过滤时按 `path` 前缀匹配整个子树，且不产生重复行。
- 密码使用 Argon2 算法加密存储。
- 错误格式：404 / 400 返回 `{"detail": "..."}`（业务校验错误如重名返回 400）；请求参数格式非法返回 422。
