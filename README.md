# sxzslz-fastapi

基于 FastAPI 的异步 Web API 服务。

## 技术栈

- **框架**: FastAPI
- **ORM**: SQLModel (基于 SQLAlchemy + Pydantic)
- **数据库**: PostgreSQL
- **异步驱动**: asyncpg
- **包管理**: uv
- **密码哈希**: argon2-cffi

## 项目结构

```
sxzslz-fastapi/
├── app/
│   ├── dao/            # 数据访问层
│   │   ├── article.py
│   │   ├── category.py
│   │   └── user.py
│   ├── models/         # 数据模型
│   │   ├── article.py
│   │   ├── category.py
│   │   └── user.py
│   ├── routers/        # 路由层（API 接口）
│   │   ├── article.py
│   │   ├── category.py
│   │   └── user.py
│   ├── service/        # 业务逻辑层
│   │   ├── article.py
│   │   ├── category.py
│   │   └── user.py
│   ├── utils/          # 工具函数
│   ├── database.py     # 数据库连接配置
│   ├── schema.py       # 通用响应模型（分页等）
│   └── settings.py     # 环境变量配置
├── main.py             # 应用入口
├── pyproject.toml      # 项目依赖
└── .env                # 环境变量（需自行创建）
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
```

### 3. 安装依赖

```bash
uv sync
```

### 4. 启动服务

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

启动后访问：
- API 文档: http://localhost:8000/docs
- ReDoc 文档: http://localhost:8000/redoc

## API 接口

### 用户模块 `/user`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/user/` | 分页获取用户列表 |

**请求参数**:
- `page`: 页码（默认 1）
- `page_size`: 每页条数（默认 10，最大 100）

**响应示例**:
```json
{
    "data": [
        {"id": 1, "nickname": "张三"},
        {"id": 2, "nickname": "李四"}
    ],
    "total": 100,
    "page": 1,
    "page_size": 10
}
```

### 分类模块 `/category`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/category/` | 获取所有分类 |

### 文章模块 `/article`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/article/` | 创建文章 |
| GET | `/article/latest` | 获取最新文章 |
| GET | `/article/recommended` | 获取推荐文章 |
| GET | `/article/detail/{slug}` | 获取文章详情 |
| GET | `/article/count` | 获取文章统计 |

**创建文章请求体**:
```json
{
    "title": "文章标题",
    "content": "文章内容",
    "category_id": 1,
    "user_id": 1,
    "is_public": true,
    "is_recommended": false
}
```

**文章详情响应**:
```json
{
    "slug": "a1b2c3d4e5f6g7h8",
    "title": "文章标题",
    "content": "文章内容",
    "category_id": 1,
    "user_id": 1,
    "view_count": 0,
    "is_public": true,
    "is_recommended": false,
    "create_at": "2026-07-13T10:00:00"
}
```

**文章统计响应**:
```json
{
    "total": 100,
    "month": 15
}
```

## 数据模型

### User
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| username | str | 用户名（唯一） |
| nickname | str | 昵称（唯一） |
| password | str | 密码（Argon2 加密） |

### Category
| 字段 | 类型 | 说明 |
|------|------|------|
| id | str | 主键 |
| name | str | 分类名称（唯一） |

### Article
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| slug | str | URL 唯一标识（自动生成） |
| title | str | 标题 |
| content | str | 内容 |
| category_id | int | 分类 ID |
| user_id | int | 作者 ID |
| create_at | datetime | 创建时间 |
| is_public | bool | 是否公开 |
| is_recommended | bool | 是否推荐 |
| view_count | int | 阅读量 |

## 开发说明

- 数据库表会在首次启动时自动创建
- 密码使用 Argon2 算法加密存储
- 文章 slug 使用 UUID 自动生成
- 404 错误会返回 `{"detail": "文章不存在"}` 格式
