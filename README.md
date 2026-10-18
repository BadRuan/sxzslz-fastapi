# sxzslz-fastapi

基于 FastAPI 的异步内容 API，提供分类 / 文章 / 图片 / 文件的管理能力，配套 JWT 鉴权。

前端对接只需关注两件事：**登录拿 token**、**按下方接口文档调用**。

## 技术栈

- **框架**: FastAPI
- **ORM**: SQLModel（SQLAlchemy + Pydantic）
- **数据库**: PostgreSQL + asyncpg
- **包管理**: uv
- **密码哈希**: argon2-cffi
- **鉴权**: JWT（PyJWT，HS256）

## 快速开始

### 环境要求

- Python 3.12+
- PostgreSQL
- [uv](https://docs.astral.sh/uv/)

### 配置 `.env`

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname
DB_ECHO=false
DEBUG=false
SECRET_KEY=your-secret-key-change-in-production
DEFAULT_USER_ID=1
CORS_ORIGINS=http://localhost:3000
ACCESS_TOKEN_EXPIRE_MINUTES=720
```

> `DEFAULT_USER_ID` 为创建文章时的默认作者 ID，需对应数据库中已存在的用户。
> `CORS_ORIGINS` 为逗号分隔的允许来源。
> `SECRET_KEY` 用于 JWT 签名，生产环境务必更换。

### 安装并启动

```bash
uv sync
uv run fastapi dev              # 开发模式，默认 127.0.0.1:8000，热重载
uv run fastapi dev --host 0.0.0.0 --port 8088   # 指定地址端口
uv run python main.py           # 生产模式，监听 0.0.0.0:8088
```

启动后可访问 Swagger 文档：<http://localhost:8000/docs>

---

## 鉴权

读接口（`GET`）公开访问；写操作（`POST` / `PATCH` / `DELETE`）需要携带 JWT。

### 1. 登录获取 token

```http
POST /auth/login
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password"
}
```

**成功响应** `200`：

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**失败响应** `401`：

```json
{"detail": "用户名或密码错误"}
```

### 2. 携带 token

之后的写操作请求都带上请求头：

```
Authorization: Bearer <access_token>
```

**Postman 用法**：Authorization → Type 选 **Bearer Token** → Token 栏粘贴 `access_token` 的值（不要带 `Bearer` 前缀，Postman 自动加）。

### 3. 获取当前登录用户

```http
GET /auth/me
Authorization: Bearer <access_token>
```

**响应** `200`：

```json
{
  "id": 4,
  "slug": "a1b2c3d4e5f6",
  "nickname": "其他"
}
```

### 错误码约定

| 状态码 | 含义 | 响应体 |
|--------|------|--------|
| 200 | 成功 | 正常数据 |
| 201 | 创建成功 | 新建资源 |
| 204 | 删除成功 | 空 |
| 400 | 业务校验失败（如重名） | `{"detail": "..."}` |
| 401 | 未认证 / token 无效 | `{"detail": "未提供认证凭据"}` |
| 404 | 资源不存在 | `{"detail": "..."}` |
| 422 | 请求参数格式非法 | FastAPI 校验错误详情 |

---

## 接口总览

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/auth/login` | ✗ | 登录，返回 JWT |
| GET | `/auth/me` | ✓ | 获取当前登录用户 |
| GET | `/base/` | ✗ | 首页基础信息（分类树 + 用户列表） |
| GET | `/categories/` | ✗ | 分类列表（扁平） |
| POST | `/categories/` | ✓ | 创建分类 |
| GET | `/categories/{id}` | ✗ | 获取单个分类 |
| PATCH | `/categories/{id}` | ✓ | 修改分类 |
| DELETE | `/categories/{id}` | ✓ | 删除分类（级联软删子树） |
| GET | `/articles/` | ✗ | 文章分页列表 |
| POST | `/articles/` | ✓ | 创建文章 |
| GET | `/articles/{slug}` | ✗ | 文章详情 |
| PATCH | `/articles/{slug}` | ✓ | 修改文章 |
| DELETE | `/articles/{slug}` | ✓ | 删除文章（软删除） |
| GET | `/image/` | ✗ | 图片分页列表 |
| POST | `/image/` | ✗ | 上传图片 |
| GET | `/image/{slug}` | ✗ | 获取图片文件 |
| GET | `/document/` | ✗ | 文件分页列表 |
| POST | `/document/` | ✗ | 上传文件 |
| GET | `/document/{slug}` | ✗ | 下载文件 |

---

## 基础信息

### GET `/base/`

返回首页需要的分类树与用户列表。

**响应** `200`：

```json
{
  "category": [
    {
      "id": 1,
      "name": "单位概况",
      "slug": "gaikuang",
      "path": "/1/",
      "level": 1,
      "sort": 0,
      "children": []
    },
    {
      "id": 8,
      "name": "财务信息",
      "slug": "caiwu",
      "path": "/8/",
      "level": 1,
      "sort": 0,
      "children": [
        {
          "id": 9,
          "name": "泵站托管",
          "slug": "tuoguan",
          "path": "/8/9/",
          "level": 2,
          "sort": 0,
          "children": []
        }
      ]
    }
  ],
  "user": [
    {"id": 1, "slug": "zhongxinzhan", "nickname": "芜湖市鸠江区沈巷镇水利站"}
  ]
}
```

---

## 分类模块 `/categories`

### GET `/categories/`

返回所有分类的扁平列表（含 `parent_id`，前端可自行组树）。

**响应** `200`：`CategoryOut` 数组

```json
[
  {
    "id": 1,
    "name": "单位概况",
    "slug": "gaikuang",
    "parent_id": 0,
    "path": "/1/",
    "level": 1,
    "sort": 0
  }
]
```

### POST `/categories/`

**请求体**：

```json
{
  "name": "财务信息",
  "slug": "caiwu",
  "parent_id": 0,
  "sort": 0
}
```

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| name | string | ✓ | — | 分类名称，对未删除分类唯一 |
| slug | string | ✓ | — | URL 标识，对未删除分类唯一 |
| parent_id | int | ✗ | 0 | 父分类 ID，`0` 表示顶级 |
| sort | int | ✗ | 0 | 排序值，越小越靠前 |

**响应** `201`：`CategoryOut`

**失败**：`400` 重名或 slug 冲突

### GET `/categories/{id}`

**响应** `200`：`CategoryOut`；`404` 分类不存在

### PATCH `/categories/{id}`

**请求体**（所有字段可选，只更新传入的字段）：

```json
{
  "name": "财务公开",
  "sort": 10
}
```

**响应** `200`：`CategoryOut`

**失败**：`400` 重名冲突；`404` 分类不存在

### DELETE `/categories/{id}`

软删除该分类，并**级联软删整棵子树**。

**响应** `204` 空；`404` 分类不存在

---

## 文章模块 `/articles`

> 文章一律以 **slug** 定位，不支持按 id 操作。

### GET `/articles/`

分页获取文章列表，支持按分类过滤。

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| page | int | 1 | 页码，从 1 开始 |
| page_size | int | 20 | 每页条数（1 ~ 100） |
| category_id | int | 无 | 按分类过滤，含其全部子分类 |

示例：`GET /articles/?page=2&page_size=10&category_id=3`

**响应** `200`：

```json
{
  "data": [
    {
      "id": 265,
      "slug": "f46bd9b7776c42e4",
      "cover_img_slug": "5894e8c2bc824d0abd7ed539115cb6b9.png",
      "title": "新版支出预算表和人员支出指标测算表",
      "is_hidden": true,
      "is_recommended": false,
      "create_at": "2026-09-24T11:22:01.682832",
      "view_count": 1,
      "like_count": 0,
      "categories": [],
      "user": {
        "id": 20,
        "slug": "jjqczj",
        "nickname": "芜湖市鸠江区财政局"
      }
    }
  ],
  "total": 265,
  "page": 1,
  "page_size": 20,
  "has_next": true
}
```

> 列表响应不含 `content` 字段，详情接口才有。

### POST `/articles/`

**请求体**：

```json
{
  "title": "文章标题",
  "content": "文章正文内容",
  "cover_img_slug": "5894e8c2bc824d0abd7ed539115cb6b9.png",
  "is_hidden": false,
  "is_recommended": true,
  "category_ids": [1, 2]
}
```

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| title | string | ✓ | — | 标题 |
| content | string | ✗ | null | 正文内容 |
| cover_img_slug | string | ✗ | null | 封面图 slug（来自图片上传接口的返回） |
| is_hidden | bool | ✗ | false | 是否隐藏 |
| is_recommended | bool | ✗ | false | 是否推荐 |
| category_ids | int[] | ✗ | [] | 关联分类 ID 列表 |

> 作者由服务端指定（`DEFAULT_USER_ID`），前端无需传。

**响应** `201`：`ArticleDetailOut`（含 `content`）

### GET `/articles/{slug}`

**响应** `200`：`ArticleDetailOut`

```json
{
  "id": 265,
  "slug": "f46bd9b7776c42e4",
  "cover_img_slug": "5894e8c2bc824d0abd7ed539115cb6b9.png",
  "title": "新版支出预算表和人员支出指标测算表",
  "content": "正文内容……",
  "is_hidden": true,
  "is_recommended": false,
  "create_at": "2026-09-24T11:22:01.682832",
  "view_count": 1,
  "like_count": 0,
  "categories": [],
  "user": {
    "id": 20,
    "slug": "jjqczj",
    "nickname": "芜湖市鸠江区财政局"
  }
}
```

**失败**：`404` 文章不存在

### PATCH `/articles/{slug}`

**请求体**（所有字段可选，只更新传入的字段）：

```json
{
  "title": "新标题",
  "is_recommended": false,
  "category_ids": [2]
}
```

**null 的语义**：

- 可空字段（`content` / `cover_img_slug` / `category_ids`）显式传 `null` 表示**清空**
- 非空字段（`title` / `is_hidden` / `is_recommended`）传 `null` 返回 `400`
- `category_ids` 传入时**整体替换**关联分类

**响应** `200`：`ArticleDetailOut`

### DELETE `/articles/{slug}`

**响应** `204` 空；`404` 文章不存在

---

## 图片模块 `/image`

### POST `/image/`

上传图片，表单字段名为 `file`。

支持格式：JPG / PNG / WebP。上传后服务端自动生成 WebP 预览图。

**请求**（`multipart/form-data`）：

```
file: <二进制图片>
```

**响应** `200`：

```json
{
  "filename": "photo.jpg",
  "slug": "5894e8c2bc824d0abd7ed539115cb6b9.png",
  "content_type": "image/jpeg"
}
```

> 返回的 `slug` 可直接用于文章的 `cover_img_slug` 字段。

**失败**：`400` 格式不支持或上传失败

### GET `/image/`

分页获取已上传图片列表。

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| page | int | 1 | 页码 |
| page_size | int | 30 | 每页条数（1 ~ 100） |

**响应** `200`：

```json
{
  "data": [
    {
      "id": 1,
      "slug": "5894e8c2bc824d0abd7ed539115cb6b9.png",
      "raw_filename": "photo.jpg",
      "mime_type": "image/jpeg",
      "size_bytes": 102400,
      "view": 0,
      "uploaded_at": "2026-10-17T10:00:00"
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 30,
  "has_next": true
}
```

### GET `/image/{slug}`

获取图片文件本体（浏览器可直接打开）。

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| file_type | string | `preview` | `raw` 返回原图；`preview` 返回 WebP 预览图 |

示例：`GET /image/5894e8c2bc824d0abd7ed539115cb6b9.png?file_type=raw`

**响应**：图片二进制流（`Content-Type` 为图片 MIME 类型）

---

## 文件模块 `/document`

### POST `/document/`

上传文档，表单字段名为 `file`。

支持格式：txt / pdf / doc / docx / xls / xlsx / ppt / pptx / zip。

**请求**（`multipart/form-data`）：

```
file: <二进制文件>
```

**响应** `200`：

```json
{
  "filename": "报告.pdf",
  "slug": "a1b2c3d4e5f6g7h8",
  "content_type": "application/pdf"
}
```

**失败**：`400` 格式不支持或上传失败

### GET `/document/`

分页获取已上传文件列表。

**查询参数**：同图片列表（`page` / `page_size`）

**响应** `200`：结构同图片列表，字段一致

### GET `/document/{slug}`

下载文件（带原始文件名）。

**响应**：文件二进制流（`Content-Disposition: attachment`）

---

## 数据模型

### User

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| slug | string | URL 唯一标识 |
| username | string | 用户名（唯一） |
| nickname | string | 昵称（唯一） |

### CategoryOut

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| name | string | 分类名称 |
| slug | string | URL 标识 |
| parent_id | int | 父分类 ID（`0` 表示顶级） |
| path | string | 层级路径，如 `/8/9/` |
| level | int | 层级深度，顶级为 1 |
| sort | int | 排序值，越小越靠前 |

### CategoryTree

在 `CategoryOut` 基础上去掉 `parent_id`，增加 `children`（子分类数组，递归结构）。

### ArticleOut / ArticleDetailOut

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| slug | string | URL 唯一标识 |
| cover_img_slug | string \| null | 封面图 slug |
| title | string | 标题 |
| content | string \| null | 正文（仅详情接口返回） |
| is_hidden | bool | 是否隐藏 |
| is_recommended | bool | 是否推荐 |
| create_at | datetime | 创建时间 |
| view_count | int | 阅读量 |
| like_count | int | 点赞数 |
| categories | CategoryTree[] | 关联分类 |
| user | UserOut \| null | 作者 |

### PageResponse

所有分页接口的统一响应结构：

| 字段 | 类型 | 说明 |
|------|------|------|
| data | T[] | 当前页数据 |
| total | int | 总记录数 |
| page | int | 当前页码 |
| page_size | int | 每页条数 |
| has_next | bool | 是否有下一页 |

---

## 开发说明

- 数据库结构由 Alembic 管理，启动时自动执行 `alembic upgrade head`。
- 既有老库首次接入需先执行 `uv run alembic stamp head`，否则迁移会因表已存在而失败。
- 分类与文章删除均为软删除（`is_deleted = true`），查询自动过滤已删除记录；分类 `name` / `slug` 软删后可复用。
- 删除分类会级联软删整棵子树。
- 文章通过 slug 定位，slug 由 UUID 自动生成。
- 文章按 `category_id` 过滤时按 `path` 前缀匹配整个子树，不会产生重复行。
- 上传文件落盘 `./uploads/` 目录。
