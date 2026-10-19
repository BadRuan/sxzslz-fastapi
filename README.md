# sxzslz-fastapi

基于 FastAPI 的异步内容 API，提供分类 / 文章 / 图片 / 文件的管理能力，配套 JWT 鉴权。

前端对接只需关注两件事：**登录拿 token**、**按下方接口文档调用**。

## 对接约定

| 约定 | 说明 |
|------|------|
| 服务地址 | 开发 `http://127.0.0.1:8000`（`fastapi dev`），生产 `http://<host>:8088`（`python main.py` / Docker）。下文路径均相对于该地址 |
| 路径尾斜杠 | 集合类路径**必须带尾斜杠**（`/articles/`、`/categories/`、`/base/` 等）。不带会返回 `307` 跳转，部分客户端对 `307` + 请求体的处理不一致 |
| 请求编码 | JSON 接口 `Content-Type: application/json`；上传接口 `multipart/form-data`，表单字段名固定为 `file` |
| 时间字段 | `create_at` / `uploaded_at` 为 ISO 8601 **本地时间、无时区后缀**（如 `2026-09-24T11:22:01.682832`），按服务器时区理解（Docker 镜像固定 `Asia/Shanghai`） |
| 分页 | 所有列表接口返回统一 `PageResponse`；`page` 超出范围时 `data` 为空数组，不报错 |
| 跨域 | 浏览器联调时前端源必须包含在服务端 `CORS_ORIGINS`（逗号分隔），否则被 CORS 拦截 |
| 上传大小 | 服务端当前**未强制限制**上传体积，建议前端自行限制（图片建议 ≤ 10MB） |
| 鉴权方式 | 读接口（`GET`）公开；写操作（`POST` / `PATCH` / `DELETE`）需 `Authorization: Bearer <token>`，见[鉴权](#鉴权) |

## 技术栈

- **框架**: FastAPI
- **ORM**: SQLModel（SQLAlchemy + Pydantic）
- **数据库**: PostgreSQL + asyncpg
- **包管理**: uv
- **密码哈希**: argon2-cffi
- **鉴权**: JWT（PyJWT，HS256）
- **图片处理**: Pillow（上传后生成 WebP 预览图）
- **测试**: pytest + pytest-asyncio（内存 SQLite，无需外部服务）

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

### 运行测试

```bash
uv run pytest                                    # 全部测试
uv run pytest tests/test_article_api.py          # 单个文件
uv run pytest tests/test_auth_api.py::test_login # 单个用例
```

测试使用内存 SQLite（`sqlite+aiosqlite://`）并通过 `httpx.ASGITransport` 走真实路由，无需 PostgreSQL，覆盖文章 / 认证 API、分类与文章的 dao/service、文件分页、启动建表（`init_db`）等行为。

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

- token 有效期由 `ACCESS_TOKEN_EXPIRE_MINUTES` 控制（默认 `720` 分钟 = 12 小时）。
- 过期或无效时写接口返回 `401`，前端应**捕获 401 → 清除本地 token → 跳转登录页**。

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
| 204 | 删除成功 | 空 body |
| 400 | 业务校验失败 | `{"detail": "具体原因"}`（**字符串**） |
| 401 | 未认证 / token 无效或过期 | `{"detail": "..."}`（**字符串**） |
| 404 | 资源不存在 | `{"detail": "..."}`（**字符串**） |
| 422 | 请求参数格式非法 | `{"detail": [...]}`（**数组**，见下方示例） |

> 解析规则：`400` / `401` / `404` 的 `detail` 是字符串，可直接展示；`422` 的 `detail` 是数组，取 `detail[0].msg` 展示。

**401 的 `detail` 取值**（均带 `WWW-Authenticate: Bearer` 响应头）：

| detail | 触发场景 |
|--------|----------|
| 未提供认证凭据 | 缺少 `Authorization` 头 |
| 无效或过期的令牌 | token 被篡改或已过期 |
| 用户不存在 | token 合法但对应用户已被删除 |

**422 示例**（创建文章缺 `title` 字段）：

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "title"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

**常见 400 业务错误文案**（`detail` 全文如下，可按需映射提示）：

| detail | 触发场景 |
|--------|----------|
| 用户名或密码错误 | 登录失败 |
| 分类名称已存在 | 创建 / 修改分类时重名 |
| 父分类不存在 | `parent_id` 指向的分类不存在 |
| 仅支持二级分类，不能创建三级分类 | 在二级分类下再挂子分类 |
| 一级分类不支持调整父级 | PATCH 给一级分类改 `parent_id` |
| 仅支持二级分类，不能调整为一级分类 | PATCH 传 `parent_id=0` |
| 父分类必须是一级分类 | 新父级本身是二级分类 |
| 存在无效的分类 | `category_ids` 含不存在的分类 id |
| 文章仅支持关联二级分类 | `category_ids` 含一级分类 id |
| 字段 title 不能为空 | PATCH 非空字段显式传 `null`（字段名随实际而变） |
| 仅支持 JPG, PNG, GIF, WebP 格式的图片 | 图片 `Content-Type` 不在白名单 |
| 仅支持txt、pdf、doc、docx、xls、xlsx、ppt、pptx、zip格式的文件 | 文件 `Content-Type` 不在白名单 |
| 上传失败 | 落盘异常 |

**404 的 `detail` 取值**：`分类不存在`、`文章不存在`、`Image not found`、`Document not found`。

---

## 接口总览

| 方法 | 路径 | 鉴权 | 说明 | 响应模型 |
|------|------|------|------|----------|
| POST | `/auth/login` | ✗ | 登录，返回 JWT | `TokenOut` |
| GET | `/auth/me` | ✓ | 获取当前登录用户 | `UserOut` |
| GET | `/base/` | ✗ | 首页基础信息（分类树 + 用户列表） | `BaseInfoOut` |
| GET | `/categories/` | ✗ | 分类列表（扁平） | `CategoryOut[]` |
| POST | `/categories/` | ✓ | 创建分类 | `CategoryOut` |
| GET | `/categories/{id}` | ✗ | 获取单个分类 | `CategoryOut` |
| PATCH | `/categories/{id}` | ✓ | 修改分类 | `CategoryOut` |
| DELETE | `/categories/{id}` | ✓ | 删除分类（级联删除子分类） | 204 空 |
| GET | `/articles/` | ✗ | 文章分页列表 | `PageResponse[ArticleOut]` |
| POST | `/articles/` | ✓ | 创建文章 | `ArticleDetailOut` |
| GET | `/articles/{slug}` | ✗ | 文章详情 | `ArticleDetailOut` |
| PATCH | `/articles/{slug}` | ✓ | 修改文章 | `ArticleDetailOut` |
| DELETE | `/articles/{slug}` | ✓ | 删除文章（软删除） | 204 空 |
| GET | `/image/` | ✗ | 图片分页列表 | `PageResponse[ImageOut]` |
| POST | `/image/` | ✗ | 上传图片 | `UploadResult` |
| GET | `/image/{slug}` | ✗ | 获取图片（默认预览图） | 二进制流 |
| GET | `/document/` | ✗ | 文件分页列表 | `PageResponse[DocumentOut]` |
| POST | `/document/` | ✗ | 上传文件 | `UploadResult` |
| GET | `/document/{slug}` | ✗ | 下载文件 | 二进制流 |

> 响应模型与[数据模型](#数据模型)章节一一对应；标 ✓ 的接口需携带 `Authorization: Bearer <token>`。

---

## 典型对接流程

以「发布一篇带封面的文章」为例：

1. **登录**：`POST /auth/login` → 保存 `access_token`，之后所有写操作带 `Authorization: Bearer <token>`。
2. **拿分类**：`GET /base/` 组导航树；管理端可用 `GET /categories/` 扁平列表自行组树。选出**二级分类** id（一级分类不能挂文章）。
3. **传封面**：`POST /image/`（`multipart/form-data`，字段名 `file`）→ 返回 `slug`。
4. **建文章**：`POST /articles/`，`cover_img_slug` 填上一步的 `slug`，`category_ids` 填二级分类 id 数组。
5. **展示封面**：`<img src="/image/{cover_img_slug}">` 默认返回已压缩的 WebP 预览图；需要原图加 `?file_type=raw`。
6. **列表分页**：`GET /articles/?page=1&page_size=20`，用响应中的 `has_next` 判断是否还有下一页；`is_hidden` / `is_recommended` 由前端自行筛选展示。

---

## 基础信息

### GET `/base/`

返回首页需要的分类树（一级 → 二级），以及用户列表。分类树节点按 `sort, id` 升序（与 `GET /categories/` 同序，可直接对照组树）。

**响应** `200`：

```json
{
  "category": [
    {
      "id": 1,
      "name": "单位概况",
      "sort": 0,
      "children": []
    },
    {
      "id": 8,
      "name": "财务信息",
      "sort": 0,
      "children": [
        {
          "id": 9,
          "name": "泵站托管",
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

> 分类为严格二级：`parent_id=0` 一级分类（仅展示分组），否则二级分类（挂文章）。

### GET `/categories/`

返回所有分类的**扁平列表**（一级、二级混在同一数组，含 `parent_id`，前端按 `parent_id` 组树），按 `sort, id` 升序（同 `sort` 时 id 小的在前）。

**响应** `200`：`CategoryOut` 数组

```json
[
  {
    "id": 1,
    "name": "单位概况",
    "parent_id": 0,
    "sort": 0
  }
]
```

### POST `/categories/`

**请求体**：

```json
{
  "name": "财务信息",
  "parent_id": 0,
  "sort": 0
}
```

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| name | string | ✓ | — | 分类名称，全局唯一 |
| parent_id | int | ✗ | 0 | 父分类 ID，`0` 表示一级分类；父分类必须是一级分类 |
| sort | int | ✗ | 0 | 排序值，越小越靠前（同级之间） |

**响应** `201`：`CategoryOut`

**失败**：`400` 重名冲突，或父分类非法（不存在 / 尝试创建三级分类）

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

| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | 分类名称 |
| parent_id | int | 二级分类可改挂到另一个一级分类下；一级分类不可调父级 |
| sort | int | 排序值（排序调整） |

**响应** `200`：`CategoryOut`

**失败**：`400` 重名冲突、父级调整非法（含 `parent_id=0` 试图升为一级）；`404` 分类不存在

### DELETE `/categories/{id}`

硬删除该分类，**级联删除子分类**，并清理文章关联（文章本体保留）。

**响应** `204` 空；`404` 分类不存在

---

## 文章模块 `/articles`

> 文章一律以 **slug** 定位，不支持按 id 操作。

### GET `/articles/`

分页获取文章列表，支持按分类过滤。按 `id` 倒序返回（最新创建在前）。

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| page | int | 1 | 页码，从 1 开始 |
| page_size | int | 20 | 每页条数（1 ~ 100） |
| category_id | int | 无 | 按**二级分类** id 精确过滤（不聚合一级分类下的子分类） |

示例：`GET /articles/?page=2&page_size=10&category_id=3`

> 列表**不过滤** `is_hidden`：隐藏文章也会返回，是否展示由前端根据 `is_hidden` 决定。

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
  "category_ids": [9, 10]
}
```

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| title | string | ✓ | — | 标题 |
| content | string | ✗ | null | 正文内容 |
| cover_img_slug | string | ✗ | null | 封面图 slug（来自图片上传接口的返回） |
| is_hidden | bool | ✗ | false | 是否隐藏 |
| is_recommended | bool | ✗ | false | 是否推荐 |
| category_ids | int[] | ✗ | [] | 关联**二级分类** ID 列表（可多个；一级分类或不存在的 id 返回 400） |

> 作者由服务端指定（`DEFAULT_USER_ID`），前端无需传。

**响应** `201`：`ArticleDetailOut`（含 `content`）

**失败**：`400` 分类无效；`422` 缺 `title` 或类型不符

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
  "category_ids": [9]
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

支持格式：JPG / PNG / GIF / WebP。上传后服务端自动生成 WebP 预览图，PNG / GIF 的**透明背景会保留**（不透明格式输出无 alpha 通道的 WebP）。

**请求**（`multipart/form-data`）：

```
file: <二进制图片>
```

- 服务端按该 part 的 `Content-Type` 做白名单校验；浏览器上传时请确保 `File.type` 非空（如 `.png` → `image/png`），为空会返回 `400`。
- 返回的 `slug` **保留原始扩展名**（如 `5894e8c2bc824d0abd7ed539115cb6b9.png`），可直接用于文章的 `cover_img_slug`。

**响应** `200`：

```json
{
  "filename": "photo.png",
  "slug": "5894e8c2bc824d0abd7ed539115cb6b9.png",
  "content_type": "image/png"
}
```

**失败**：`400` 格式不支持或上传失败

### GET `/image/`

分页获取已上传图片列表。按 `id` 倒序（最新上传在前）。

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
      "raw_filename": "photo.png",
      "mime_type": "image/png",
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

获取图片文件本体（浏览器可直接打开）。每次成功访问自增浏览量（列表中的 `view` 字段）。

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| file_type | string | `preview` | `raw` 返回原图；`preview` 返回 WebP 预览图（**固定 WebP 格式**，`Content-Type: image/webp`） |

示例：`GET /image/5894e8c2bc824d0abd7ed539115cb6b9.png?file_type=raw`

**响应**：图片二进制流（`raw` 时 `Content-Type` 为原图 MIME 类型）

**失败**：`404` 图片记录不存在

> 图片模块暂无删除接口。

---

## 文件模块 `/document`

### POST `/document/`

上传文档，表单字段名为 `file`。

支持格式：txt / pdf / doc / docx / xls / xlsx / ppt / pptx / zip。

**请求**（`multipart/form-data`）：

```
file: <二进制文件>
```

- 与图片上传一致：按 part 的 `Content-Type` 白名单校验，浏览器端请确保 `File.type` 非空。
- 返回的 `slug` 保留原始扩展名，可用于下载链接 `GET /document/{slug}`。

**响应** `200`：

```json
{
  "filename": "报告.pdf",
  "slug": "a1b2c3d4e5f6g7h8.pdf",
  "content_type": "application/pdf"
}
```

**失败**：`400` 格式不支持或上传失败

### GET `/document/`

分页获取已上传文件列表。按 `id` 倒序（最新上传在前）。

**查询参数**：同图片列表（`page` 默认 1、`page_size` 默认 30，1 ~ 100）

**响应** `200`：`PageResponse[DocumentOut]`，结构与字段同图片列表

### GET `/document/{slug}`

下载文件（带原始文件名）。每次成功访问自增浏览量（列表中的 `view` 字段）。

**响应**：文件二进制流（`Content-Disposition: attachment`，`Content-Type` 为上传时的 MIME 类型）

**失败**：`404` 文件记录不存在

> 文件模块暂无删除接口。

---

## 数据模型

> 所有时间字段为 ISO 8601 本地时间（无时区后缀），见[对接约定](#对接约定)。

### TokenOut

| 字段 | 类型 | 说明 |
|------|------|------|
| access_token | string | JWT，放 `Authorization: Bearer <此处>` |
| token_type | string | 固定 `"bearer"` |

### UserOut

登录态、作者信息、`/base/` 用户列表均用此结构；**不返回** `username` / 密码。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| slug | string | URL 唯一标识 |
| nickname | string | 昵称（展示名） |

### BaseInfoOut

| 字段 | 类型 | 说明 |
|------|------|------|
| category | CategoryTree[] | 分类树（一级 → 二级） |
| user | UserOut[] | 用户列表 |

### CategoryOut

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| name | string | 分类名称（全局唯一） |
| parent_id | int | 父分类 ID（`0` 一级分类，否则二级分类） |
| sort | int | 排序值，越小越靠前 |

### CategoryTree

在 `CategoryOut` 基础上去掉 `parent_id`，增加 `children`（下级分类数组，二级分类的 `children` 恒为 `[]`）。

### ArticleOut / ArticleDetailOut

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| slug | string | URL 唯一标识（操作文章的唯一键） |
| cover_img_slug | string \| null | 封面图 slug，用于 `GET /image/{slug}` |
| title | string | 标题 |
| content | string \| null | 正文（**仅详情 / 创建 / 修改响应返回**，列表不含） |
| is_hidden | bool | 是否隐藏（列表接口不过滤，前端自行决定展示） |
| is_recommended | bool | 是否推荐 |
| create_at | datetime | 创建时间 |
| view_count | int | 阅读量（只读，当前无自增接口） |
| like_count | int | 点赞数（只读，当前无点赞接口） |
| categories | CategoryTree[] | 关联分类（二级分类，可为空数组） |
| user | UserOut \| null | 作者，可能为 `null` |

### UploadResult

| 字段 | 类型 | 说明 |
|------|------|------|
| filename | string | 原始文件名 |
| slug | string | 文件标识（含原始扩展名），用于后续 GET / 文章封面 |
| content_type | string | 上传时的 MIME 类型 |

### ImageOut / DocumentOut

两者结构一致：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| slug | string | 文件标识（含原始扩展名） |
| raw_filename | string | 原始文件名 |
| mime_type | string | 上传时的 MIME 类型 |
| size_bytes | int | 原始文件大小（字节） |
| view | int | 浏览量（每次成功 GET 自增） |
| uploaded_at | datetime | 上传时间 |

### PageResponse

所有分页接口的统一响应结构：

| 字段 | 类型 | 说明 |
|------|------|------|
| data | T[] | 当前页数据（超界为空数组） |
| total | int | 总记录数 |
| page | int | 当前页码 |
| page_size | int | 每页条数 |
| has_next | bool | 是否有下一页 |

---

## 项目结构

分层调用：`routers → service → dao → model`，请求/响应模型集中在 `app/schema/`。

```
main.py                  # 入口：挂载路由、CORS、lifespan 启动建表
app/
├── routers/             # 路由层：参数校验、异常 → HTTP 状态码
├── service/             # 业务层：校验、分页组装，ValueError → 400
├── dao/                 # 数据层：SQLModel 查询，只 flush 不 commit
├── model/               # 表模型（Category / Article / Image / Document / User）
├── schema/              # 请求 / 响应 Pydantic 模型
├── auth.py              # JWT 签发与校验（get_current_user）
├── settings.py          # .env 配置、上传目录、MIME 白名单
├── database.py          # 引擎、请求级会话（自动 commit/rollback）、init_db
└── utils/               # WebP 预览图生成
tests/                   # pytest 用例与 fixtures（conftest.py）
uploads/                 # 上传落盘目录（已 gitignore）
```

---

## 部署（Docker）

```bash
docker build -t sxzslz-fastapi .
docker run -d -p 8088:8088 \
  -v $(pwd)/uploads:/app/uploads \
  --env-file .env \
  sxzslz-fastapi
```

- 镜像基于 `python:3.12-slim`，用 `requirements.txt`（pip 钉死版本）安装依赖，容器内监听 **0.0.0.0:8088**（`python main.py`）。
- `.env` 已被 `.dockerignore` 排除，不进镜像；配置通过 `--env-file` 或 `-e` 在运行时注入。
- `uploads/` 挂载为持久化卷，避免重建容器丢失上传文件。

---

## 开发说明

- 启动时自动执行一次 `init_db()` 建表（`SQLModel.metadata.create_all`，幂等，已存在的表跳过）。
- `create_all` 不会修改已有表结构；调整字段后需对存量库手动执行 DDL，或清库重建。
- 文章删除为软删除（`is_deleted = true`）；分类为**硬删除**（级联删除子分类并清理关联），分类 `name` 删除后可复用。
- 文章通过 slug 定位，slug 由 UUID 自动生成。
- 文章只能关联二级分类；按 `category_id` 过滤时精确匹配该分类，不聚合子分类。
- 表间关联不使用数据库外键，由业务层维护（`article_category` 关联表）。
- 上传文件落盘 `./uploads/` 目录。
- `requirements.txt` 是给 Docker（pip）用的**钉死版本快照**，由 `uv export --no-dev --no-hashes -o requirements.txt` 生成——改动 `pyproject.toml` 依赖后需重新导出同步，勿手改。
- 项目**无 lint / typecheck / formatter / CI 配置**；包管理与依赖锁以 `pyproject.toml` + `uv.lock` 为准。
