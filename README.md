# sxzslz-fastapi

基于 FastAPI 的异步内容 API，提供分类 / 文章 / 图片 / 文件的管理能力，配套 JWT 鉴权。

前端对接只需关注两件事：**登录拿 token**、**按下方接口文档调用**。

> 📄 **前端同学请直接看 [docs/frontend-api.md](docs/frontend-api.md)**：面向对接的完整文档，含鉴权流程、错误处理、全部接口的真实响应示例与 FAQ。

## 对接约定

| 约定 | 说明 |
|------|------|
| 服务地址 | 开发 `http://127.0.0.1:8000`（`fastapi dev`），生产 `http://<host>:8088`（`python main.py` / Docker）。下文路径均相对于该地址 |
| 路径尾斜杠 | 集合类路径**必须带尾斜杠**（`/articles/`、`/categories/`、`/base/` 等）。不带会返回 `307` 跳转，部分客户端对 `307` + 请求体的处理不一致 |
| 请求编码 | JSON 接口 `Content-Type: application/json`；上传接口 `multipart/form-data`。单文件上传字段名固定为 `file`；批量上传字段名固定为 `files`（同名 part 重复） |
| 时间字段 | `create_at` / `uploaded_at` 为 ISO 8601 **本地时间、无时区后缀**（如 `2026-09-24T11:22:01.682832`），按服务器时区理解（Docker 镜像固定 `Asia/Shanghai`） |
| 分页 | 所有列表接口返回统一 `PageResponse`；`page` 超出范围时 `data` 为空数组，不报错 |
| 跨域 | 浏览器联调时前端源必须包含在服务端 `CORS_ORIGINS`（逗号分隔），否则被 CORS 拦截 |
| 上传大小 | 服务端强制限制：图片默认 **10MB**（`MAX_IMAGE_SIZE_MB`）、文档默认 **50MB**（`MAX_DOCUMENT_SIZE_MB`），超出返回 `400`；空文件返回 `400 文件内容为空`。进度条与取消见 `docs/frontend-api.md` 的 `uploadWithProgress` |
| 鉴权方式 | 文章/分类/图片本体等 **GET 公开**；图片列表、文档列表/下载、全部写操作需 `Authorization: Bearer <token>`。超管（`is_superuser`，默认账号 `ruanfumin`）可管理全部资源，见[角色权限](#角色权限) |

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
MAX_IMAGE_SIZE_MB=10
MAX_DOCUMENT_SIZE_MB=50
```

> `DEFAULT_USER_ID` 为创建文章时的默认作者 ID，需对应数据库中已存在的用户。
> `CORS_ORIGINS` 为逗号分隔的允许来源。
> `SECRET_KEY` 用于 JWT 签名，生产环境务必更换。
> `MAX_IMAGE_SIZE_MB` / `MAX_DOCUMENT_SIZE_MB` 为上传大小上限（MB），超出返回 `400`。

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

文章 / 分类 / 图片本体（`GET /image/{slug}`）等前台接口公开；**图片列表、文档列表与下载、全部写操作**需要 JWT。

### 角色权限

| 角色 | 判定 | 能力 |
|------|------|------|
| 超级管理员 | `user.is_superuser = true`（默认账号 `ruanfumin`；存量库执行 `uv run python scripts/migrate_add_is_superuser.py`） | 任意文章可改/删/恢复，并可指定作者 `user_id` 与发布时间 `create_at`；可见/可改/可删全部图片与文档；可创建/删除普通账户、重置普通账户密码为 `abc123` |
| 普通用户 | 其余账号 | 仅操作**自己**的文章与上传文件；列表只见自己上传的；`view_count` / `like_count` 不可 PATCH |

前端可从 `/auth/me` 或 `/base/` 的 `user[].is_superuser` 判断角色，控制管理入口显隐。

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
  "nickname": "其他",
  "is_superuser": false
}
```

### 4. 修改密码

```http
PUT /auth/password
Authorization: Bearer <access_token>
Content-Type: application/json

{"old_password": "当前密码", "new_password": "新密码（至少 6 位）"}
```

**响应** `200`：`{"detail": "密码修改成功"}`

**失败**：`400` 原密码错误；`401` 未登录 / token 无效；`422` 新密码不足 6 位或缺字段。修改成功后旧 token 在过期前仍有效，前端应引导用户用新密码重新登录。

### 错误码约定

| 状态码 | 含义 | 响应体 |
|--------|------|--------|
| 200 | 成功 | 正常数据 |
| 201 | 创建成功 | 新建资源 |
| 204 | 删除成功 | 空 body |
| 400 | 业务校验失败 | `{"detail": "具体原因"}`（**字符串**） |
| 401 | 未认证 / token 无效或过期 | `{"detail": "..."}`（**字符串**） |
| 403 | 已登录但无权操作 | `{"detail": "..."}`（**字符串**） |
| 404 | 资源不存在 | `{"detail": "..."}`（**字符串**） |
| 422 | 请求参数格式非法 | `{"detail": [...]}`（**数组**，见下方示例） |
| 500 | 服务器内部未预期异常 | `{"detail": "服务器内部错误"}`（**字符串**） |

> 解析规则：`400` / `401` / `403` / `404` / `500` 的 `detail` 是字符串，可直接展示；`422` 的 `detail` 是数组，取 `detail[0].msg` 展示。

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

**常见 400 / 403 业务错误文案**（`detail` 全文如下，可按需映射提示）：

| 状态码 | detail | 触发场景 |
|--------|--------|----------|
| 400 | 用户名或密码错误 | 登录失败 |
| 400 | 原密码错误 | 修改密码时旧密码不匹配 |
| 400 | 父分类不存在 | `parent_id` 指向的分类不存在 |
| 400 | 仅支持二级分类，不能创建三级分类 | 在二级分类下再挂子分类 |
| 400 | 一级分类不支持调整父级 | PATCH 给一级分类改 `parent_id` |
| 400 | 仅支持二级分类，不能调整为一级分类 | PATCH 传 `parent_id=0` |
| 400 | 父分类必须是一级分类 | 新父级本身是二级分类 |
| 400 | 存在无效的分类 | `category_ids` 含不存在的分类 id |
| 400 | 文章仅支持关联二级分类 | `category_ids` 含一级分类 id |
| 400 | 字段 title 不能为空 | PATCH 非空字段显式传 `null`（字段名随实际而变） |
| 400 | 图片大小超过限制（最大 10MB） | 图片超 `MAX_IMAGE_SIZE_MB` |
| 400 | 文件大小超过限制（最大 50MB） | 文档超 `MAX_DOCUMENT_SIZE_MB` |
| 400 | 文件内容为空 | 上传 0 字节文件 |
| 400 | 服务器磁盘空间已满，请联系管理员清理后重试 | 落盘 ENOSPC |
| 400 | `不支持的图片类型「…」，仅支持 JPG、PNG、GIF、WebP、BMP、TIFF、ICO 格式` | 图片 `Content-Type` 不在白名单 |
| 400 | `不支持的文件类型「…」，仅支持 txt、csv、md、rtf、pdf、doc、docx、docm、xls、xlsx、xlsm、ppt、pptx、pptm、odt、ods、odp、zip、7z、rar、gz、tar、epub 格式` | 文档 `Content-Type` 不在白名单 |
| 403 | 无权指定其他用户发布 | 普通用户创建文章传他人 `user_id` |
| 403 | 无权修改他人文章 / 无权删除他人文章 / 无权恢复他人文章 | 文章写操作非作者且非超管 |
| 403 | 无权限操作该文件 | 图片/文档改名或删除非本人且非超管 |
| 403 | 无权限查看该文件 | 下载他人文档 |

**404 的 `detail` 取值**：`分类不存在`、`文章不存在`、`Image not found`、`Document not found`。

---

## 用户账户管理 `/users`

> 仅超级管理员（`is_superuser=true`）可调用；普通用户 → `403 仅超级管理员可管理用户账户`。无注册接口，普通账户统一由超管创建。

### POST `/users/`

创建普通账户。**仅超管**。密码可省略，缺省为 `abc123`（`DEFAULT_USER_PASSWORD`）。

```json
{"username": "zhangsan", "nickname": "张三", "password": "abc123"}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | ✓ | 登录名，唯一 |
| nickname | string | ✓ | 展示名，唯一 |
| password | string | ✗ | 至少 6 位；缺省 `abc123` |

**响应** `201`：`UserOut`（`{id, slug, nickname, is_superuser: false}`）。`is_superuser` 不可通过该接口设置。

**失败**：`400 用户名已存在` / `400 昵称已存在`；`403` 非超管；`422` 字段缺失或密码不足 6 位。

### POST `/users/{id}/reset-password`

把**普通账户**密码重置为 `abc123`（`DEFAULT_USER_PASSWORD`），**仅超管**。

**响应** `200`：`{"detail": "密码已重置为 abc123"}`。重置后旧密码立即失效。

**失败**：`403 不能重置超级管理员密码`；`404 用户不存在`；`403` 非超管。

### DELETE `/users/{id}`

删除**普通账户**，**仅超管**。**硬删除**：账户行删除后无法登录（已签发 token 也会因「用户不存在」失效）。

> 该账户已发布的文章、已上传的图片/文档**保留**，`user` 关联变为 `null`（无数据库外键）；如需清理内容请先单独删除。

**响应** `204` 空。**失败**：`403 不能删除超级管理员账户`；`404 用户不存在`；`403` 非超管。

---

## 接口总览

| 方法 | 路径 | 鉴权 | 说明 | 响应模型 |
|------|------|------|------|----------|
| POST | `/auth/login` | ✗ | 登录，返回 JWT | `TokenOut` |
| GET | `/auth/me` | ✓ | 获取当前登录用户 | `UserOut` |
| PUT | `/auth/password` | ✓ | 修改当前用户密码 | `{"detail": ...}` |
| POST | `/users/` | ✓ | 创建普通账户（仅超管，密码缺省 abc123） | `UserOut` |
| POST | `/users/{id}/reset-password` | ✓ | 重置普通账户密码为 abc123（仅超管） | `{"detail": ...}` |
| DELETE | `/users/{id}` | ✓ | 删除普通账户（仅超管，内容保留） | 204 空 |
| GET | `/base/` | ✗ | 首页基础信息（分类树 + 用户列表） | `BaseInfoOut` |
| GET | `/categories/` | ✗ | 分类列表（扁平） | `CategoryOut[]` |
| POST | `/categories/` | ✓ | 创建分类 | `CategoryOut` |
| GET | `/categories/{id}` | ✗ | 获取单个分类 | `CategoryOut` |
| PATCH | `/categories/{id}` | ✓ | 修改分类 | `CategoryOut` |
| DELETE | `/categories/{id}` | ✓ | 删除分类（级联删除子分类） | 204 空 |
| GET | `/articles/` | ✗ | 文章分页列表 | `PageResponse[ArticleOut]` |
| POST | `/articles/` | ✓ | 创建文章（超管可指定作者/时间） | `ArticleDetailOut` |
| POST | `/articles/batch-category` | ✓ | 批量加入/移出分类 | `ArticleBatchCategoryOut` |
| GET | `/articles/{slug}` | ✗ | 文章详情 | `ArticleDetailOut` |
| POST | `/articles/{slug}/like` | ✗ | 匿名点赞（+1） | `ArticleLikeOut` |
| PATCH | `/articles/{slug}` | ✓ | 修改文章（作者或超管） | `ArticleDetailOut` |
| DELETE | `/articles/{slug}` | ✓ | 删除文章（软删除 → 回收站） | 204 空 |
| POST | `/articles/{slug}/restore` | ✓ | 恢复回收站文章 | `ArticleDetailOut` |
| GET | `/image/` | ✓ | 图片分页列表（超管全部 / 普通仅自己） | `PageResponse[ImageOut]` |
| POST | `/image/` | ✓ | 上传图片（支持进度+取消） | `UploadResult` |
| POST | `/image/batch/` | ✓ | 批量上传图片（多文件同时，整批原子） | `UploadResult[]` |
| GET | `/image/{slug}` | ✗ | 获取图片本体（默认预览图，公开） | 二进制流 |
| PATCH | `/image/{slug}` | ✓ | 改图片展示名（本人或超管） | `ImageOut` |
| DELETE | `/image/{slug}` | ✓ | 删除图片（本人或超管，清磁盘） | 204 空 |
| GET | `/document/` | ✓ | 文件分页列表（超管全部 / 普通仅自己） | `PageResponse[DocumentOut]` |
| POST | `/document/` | ✓ | 上传文件（支持进度+取消） | `UploadResult` |
| POST | `/document/batch/` | ✓ | 批量上传文件（多文件同时，整批原子） | `UploadResult[]` |
| PATCH | `/document/{slug}` | ✓ | 改文件展示名（本人或超管） | `DocumentOut` |
| DELETE | `/document/{slug}` | ✓ | 删除文件（本人或超管，清磁盘） | 204 空 |
| GET | `/document/{slug}` | ✓ | 下载文件（本人或超管） | 二进制流 |

> 响应模型与[数据模型](#数据模型)章节一一对应；标 ✓ 的接口需携带 `Authorization: Bearer <token>`。

---

## 典型对接流程

以「发布一篇带封面的文章」为例：

1. **登录**：`POST /auth/login` → 保存 `access_token`，之后所有写操作带 `Authorization: Bearer <token>`。
2. **拿分类**：`GET /base/` 组导航树；管理端可用 `GET /categories/` 扁平列表自行组树。选出**二级分类** id（一级分类不能挂文章）。
3. **传封面**：`POST /image/`（`multipart/form-data`，字段名 `file`）→ 返回 `slug`。
4. **建文章**：`POST /articles/`，`cover_img_slug` 填上一步的 `slug`，`category_ids` 填二级分类 id 数组。
5. **展示封面**：`<img src="/image/{cover_img_slug}">` 默认返回已压缩的 WebP 预览图；需要原图加 `?file_type=raw`。
6. **列表分页**：`GET /articles/?page=1&page_size=20`，用响应中的 `has_next` 判断是否还有下一页；回收站文章由服务端过滤，`is_recommended` 由前端自行筛选展示。

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
    {"id": 1, "slug": "zhongxinzhan", "nickname": "芜湖市鸠江区沈巷镇水利站", "is_superuser": false}
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
| name | string | ✓ | — | 分类名称（**允许重名**，不同父级下常见同名） |
| parent_id | int | ✗ | 0 | 父分类 ID，`0` 表示一级分类；父分类必须是一级分类 |
| sort | int | ✗ | 0 | 排序值，越小越靠前（同级之间） |

**响应** `201`：`CategoryOut`

**失败**：`400` 父分类非法（不存在 / 尝试创建三级分类）

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

**失败**：`400` 父级调整非法（含 `parent_id=0` 试图升为一级）；`404` 分类不存在

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
| user_id | int | 无 | 按作者用户 id 过滤（后台展示登录账户的文章） |
| is_deleted | bool | false | `false` 只返回未删除文章；`true` 只返回回收站文章（后台用） |

示例：`GET /articles/?page=2&page_size=10&category_id=3&user_id=1`

> 可见性由服务端的 `is_deleted` 统一过滤：前台/普通列表永远拿不到已删文章，后台回收站传 `is_deleted=true` 即可枚举被删文章再恢复。

**响应** `200`：

```json
{
  "data": [
    {
      "id": 265,
      "slug": "f46bd9b7776c42e4",
      "cover_img_slug": "5894e8c2bc824d0abd7ed539115cb6b9.png",
      "title": "新版支出预算表和人员支出指标测算表",
      "is_deleted": false,
      "is_recommended": false,
      "create_at": "2026-09-24T11:22:01.682832",
      "view_count": 1,
      "like_count": 0,
      "user_id": 20,
      "categories": [],
      "user": {
        "id": 20,
        "slug": "jjqczj",
        "nickname": "芜湖市鸠江区财政局",
        "is_superuser": false
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
  "is_recommended": true,
  "category_ids": [9, 10]
}
```

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| title | string | ✓ | — | 标题 |
| content | string | ✗ | null | 正文内容 |
| cover_img_slug | string | ✗ | null | 封面图 slug（来自图片上传接口的返回） |
| is_recommended | bool | ✗ | false | 是否推荐 |
| category_ids | int[] | ✗ | [] | 关联**二级分类** ID 列表（可多个；一级分类或不存在的 id 返回 400） |
| user_id | int | ✗ | 当前登录用户 | **仅超管**：指定发布主体；普通用户传他人 → `403 无权指定其他用户发布` |
| create_at | datetime | ✗ | 服务器当前时间 | **仅超管**：指定发布时间；普通用户传入被忽略 |

> 默认作者为当前登录用户（取自 JWT）。`DEFAULT_USER_ID` 仅作为不走 API 直接调用 service 时的兜底默认。

**响应** `201`：`ArticleDetailOut`（含 `content`）

**失败**：`400` 分类无效；`403` 普通用户指定他人为作者；`422` 缺 `title` 或类型不符

### GET `/articles/{slug}`

**响应** `200`：`ArticleDetailOut`

```json
{
  "id": 265,
  "slug": "f46bd9b7776c42e4",
  "cover_img_slug": "5894e8c2bc824d0abd7ed539115cb6b9.png",
  "title": "新版支出预算表和人员支出指标测算表",
  "content": "正文内容……",
  "is_deleted": false,
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

**权限**：作者本人或超管；他人 → `403 无权修改他人文章`。

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
- 非空字段（`title` / `is_recommended` / `user_id` / `create_at`）传 `null` 返回 `400`
- `category_ids` 传入时**整体替换**关联分类
- `is_deleted` 不走 PATCH：删除用 `DELETE`，恢复用 `POST /articles/{slug}/restore`

**超管专属**（普通用户请求中出现会被忽略）：`user_id` 改作者、`create_at` 改发布时间。`view_count` / `like_count` 对所有人不可 PATCH。

**响应** `200`：`ArticleDetailOut`

### POST `/articles/{slug}/like`

匿名点赞：公开接口（无需 token），每次调用 `like_count` +1。前端可配合 localStorage 限制同一浏览器重复点赞。

**响应** `200`：

```json
{"like_count": 12}
```

**失败**：`404` 文章不存在或已删除

### DELETE `/articles/{slug}`

软删除：文章移入回收站（`is_deleted = true`），前台列表/详情/点赞/修改一律不可达（`404`），后台可用 `GET /articles/?is_deleted=true` 找回。

**响应** `204` 空；`404` 文章不存在（或已在回收站）

### POST `/articles/{slug}/restore`

恢复回收站文章：`is_deleted` 置回 `false`，文章重新出现在正常列表。需携带 token；对未删除文章调用是幂等空操作。

**响应** `200`：`ArticleDetailOut`

**失败**：`401` 未登录；`404` 文章不存在

### POST `/articles/batch-category`

批量将多篇文章**加入**或**移出**一个二级分类（后台勾选操作）。需携带 token。

**请求体**：

```json
{
  "slugs": ["f46bd9b7776c42e4", "05ec0dc53ad942ad"],
  "category_id": 9,
  "mode": "add"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| slugs | string[] | ✓ | 文章 slug 列表（至少 1 个，去重后处理） |
| category_id | int | ✓ | 目标分类 ID（必须是二级分类） |
| mode | string | ✓ | `add` 加入 / `remove` 移出 |

**语义**：幂等——`add` 只补缺失关联（不产生重复），`remove` 不在该分类也计数；只操作未删除文章。

**响应** `200`：

```json
{"affected": 2}
```

**失败**：`401` 未登录；`400` 一级分类 / 分类不存在 / 任一 slug 不存在或已删除（整批不生效）；`422` slugs 为空或 mode 非法

---

## 图片模块 `/image`

### POST `/image/`

上传图片，表单字段名为 `file`。**需携带 token**（未登录返回 `401`）。

**支持格式**：JPG、PNG、GIF、WebP、BMP、TIFF、ICO（按 `Content-Type` 白名单，PIL 均可生成 WebP 预览）。上传后自动生成 WebP 预览图，PNG / GIF 的**透明背景会保留**。

**请求**（`multipart/form-data`）：

```
file: <二进制图片>
```

- 服务端按该 part 的 `Content-Type` 做白名单校验；浏览器上传时请确保 `File.type` 非空（如 `.png` → `image/png`），为空会返回 `400`。
- 返回的 `slug` **保留原始扩展名**（如 `5894e8c2bc824d0abd7ed539115cb6b9.png`），可直接用于文章的 `cover_img_slug`。
- 默认大小上限 **10MB**（`MAX_IMAGE_SIZE_MB`），超出或空文件返回 `400`。
- **进度 + 取消**：用 `XMLHttpRequest.upload.onprogress` + `AbortController`，完整封装见 `docs/frontend-api.md` 的 `uploadWithProgress`（图片/文档共用）；中途取消服务端会清理半成品。

**响应** `200`：

```json
{
  "filename": "photo.png",
  "slug": "5894e8c2bc824d0abd7ed539115cb6b9.png",
  "content_type": "image/png",
  "size_bytes": 102400,
  "url": "/image/5894e8c2bc824d0abd7ed539115cb6b9.png",
  "raw_url": "/image/5894e8c2bc824d0abd7ed539115cb6b9.png?file_type=raw"
}
```

> `url` 为预览图相对地址，`raw_url` 为原图地址；前端拼 `BASE` 后可直接 `<img src>`。

### POST `/image/batch/`

一次上传多张图片，表单字段名 **`files`**（每个文件一个同名 part）。**需携带 token**（未登录返回 `401`）。

**请求**（`multipart/form-data`）：

```
files: <二进制图片1>
files: <二进制图片2>
```

- 单次最多 **20** 个文件（`MAX_BATCH_FILES`），超出返回 `400`。
- 类型白名单、单文件大小上限（10MB）、空文件校验与 `POST /image/` 一致；先整批校验类型再逐个落盘。
- **整批原子**：任一文件失败 → `400` 整批不生效，不产生部分记录、不残留磁盘文件；`detail` 标明第几个文件（如 `第 2 个文件「bad.png」：...`）。

**响应** `200`：`UploadResult[]`，顺序与请求 `files` 一致：

```json
[
  {
    "filename": "a.png",
    "slug": "5894e8c2bc824d0abd7ed539115cb6b9.png",
    "content_type": "image/png",
    "size_bytes": 102400,
    "url": "/image/5894e8c2bc824d0abd7ed539115cb6b9.png",
    "raw_url": "/image/5894e8c2bc824d0abd7ed539115cb6b9.png?file_type=raw"
  }
]
```

**失败**：`400`（逐文件原因）/ `401` 未登录 / `422` 未携带文件。

**失败**：`400` 见 `docs/frontend-api.md` 上传失败详情表；`401` 未登录。

### GET `/image/`

**需登录**。分页获取已上传图片列表。按 `id` 倒序（最新上传在前）。**超管见全部；普通用户只见自己上传的**。

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
      "user_id": 20,
      "view": 0,
      "uploaded_at": "2026-10-17T10:00:00",
      "user": {
        "id": 20,
        "slug": "jjqczj",
        "nickname": "芜湖市鸠江区财政局",
        "is_superuser": false
      }
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 30,
  "has_next": true
}
```

> `user` 为上传者（业务层关联）；对应用户不存在时为 `null`。

### GET `/image/{slug}`

**公开**（文章封面等前台依赖此接口，不限制上传者）。获取图片文件本体。每次成功访问自增浏览量（列表中的 `view` 字段）。

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| file_type | string | `preview` | `raw` 返回原图；`preview` 返回 WebP 预览图（**固定 WebP 格式**，`Content-Type: image/webp`） |

示例：`GET /image/5894e8c2bc824d0abd7ed539115cb6b9.png?file_type=raw`

**响应**：图片二进制流（`raw` 时 `Content-Type` 为原图 MIME 类型）

**失败**：`404` 图片记录不存在

### PATCH `/image/{slug}`

仅**上传者本人或超管**可改展示名。请求体 `{"raw_filename": "新名字.png"}`（1~255 字符）。

**响应** `200`：`ImageOut`。**失败**：`401`；`403 无权限操作该文件`；`404`；`422`。

### DELETE `/image/{slug}`

仅**上传者本人或超管**可删：DB 记录 + 原图 + WebP 预览图一并清理（硬删，不可恢复）。

**响应** `204` 空。**失败**：`401`；`403`；`404`。

---

## 文件模块 `/document`

### POST `/document/`

上传文档，表单字段名为 `file`。**需携带 token**（未登录返回 `401`）。

**支持格式**：txt、csv、md、rtf、pdf、doc/docx/docm、xls/xlsx/xlsm、ppt/pptx/pptm、odt/ods/odp、zip/7z/rar/gz/tar、epub（完整 MIME 表见 `docs/frontend-api.md`）。

**请求**（`multipart/form-data`）：

```
file: <二进制文件>
```

- 与图片上传一致：按 part 的 `Content-Type` 白名单校验，浏览器端请确保 `File.type` 非空。
- 返回的 `slug` 保留原始扩展名，可用于下载链接 `GET /document/{slug}`（需带 token）。
- 默认大小上限 **50MB**（`MAX_DOCUMENT_SIZE_MB`），超出或空文件返回 `400`。
- **进度 + 取消**：与图片共用 `uploadWithProgress`（见 `docs/frontend-api.md`），支持 `AbortController` 中途取消。

**响应** `200`：

```json
{
  "filename": "报告.pdf",
  "slug": "a1b2c3d4e5f6g7h8.pdf",
  "content_type": "application/pdf",
  "size_bytes": 8,
  "url": "/document/a1b2c3d4e5f6g7h8.pdf",
  "raw_url": null
}
```

> `url` 为下载相对地址；`raw_url` 固定 `null`（文档无预览/原图之分）。

### POST `/document/batch/`

一次上传多个文件，表单字段名 **`files`**（每个文件一个同名 part）。**需携带 token**（未登录返回 `401`）。

**请求**（`multipart/form-data`）：

```
files: <二进制文件1>
files: <二进制文件2>
```

- 单次最多 **20** 个文件（`MAX_BATCH_FILES`），超出返回 `400`。
- 类型白名单、单文件大小上限（50MB）、空文件校验与 `POST /document/` 一致；先整批校验类型再逐个落盘。
- **整批原子**：任一文件失败 → `400` 整批不生效，不产生部分记录、不残留磁盘文件；`detail` 标明第几个文件。

**响应** `200`：`UploadResult[]`（`raw_url` 恒为 `null`），顺序与请求 `files` 一致：

```json
[
  {
    "filename": "报告.pdf",
    "slug": "a1b2c3d4e5f6g7h8.pdf",
    "content_type": "application/pdf",
    "size_bytes": 20480,
    "url": "/document/a1b2c3d4e5f6g7h8.pdf",
    "raw_url": null
  }
]
```

**失败**：`400`（逐文件原因）/ `401` 未登录 / `422` 未携带文件。

**失败**：`400` 格式不支持 / 超过大小限制 / 空文件 / 上传失败

### GET `/document/`

**需登录**。分页获取已上传文件列表。**超管见全部；普通用户只见自己上传的**。

**查询参数**：同图片列表（`page` 默认 1、`page_size` 默认 30，1 ~ 100），另支持 `sort` 排序字段（均倒序，非法值 422）：

| 值 | 含义 |
| --- | --- |
| `uploaded_at`（默认） | 按上传时间倒序，最新上传在前 |
| `view` | 按浏览量倒序，最热在前 |

**响应** `200`：`PageResponse[DocumentOut]`（字段同图片列表，含 `user_id` 与上传者 `user`）：

```json
{
  "data": [
    {
      "id": 3,
      "slug": "a1b2c3d4e5f6g7h8.pdf",
      "raw_filename": "报告.pdf",
      "mime_type": "application/pdf",
      "size_bytes": 20480,
      "user_id": 20,
      "view": 12,
      "uploaded_at": "2026-10-17T10:05:00",
      "user": {
        "id": 20,
        "slug": "jjqczj",
        "nickname": "芜湖市鸠江区财政局",
        "is_superuser": false
      }
    }
  ],
  "total": 40,
  "page": 1,
  "page_size": 30,
  "has_next": true
}
```

### GET `/document/{slug}`

**需登录**。下载文件（带原始文件名）。每次成功访问自增浏览量（列表中的 `view` 字段）。

**权限**：上传者本人或超管；他人 → `403 无权限查看该文件`。`window.open` 无法带自定义头时用 `fetch` + `Authorization` 转 blob。

**响应**：文件二进制流（`Content-Disposition: attachment`，`Content-Type` 为上传时的 MIME 类型）

**失败**：`401`；`403 无权限查看该文件`；`404` 文件记录不存在

### PATCH `/document/{slug}`

仅**上传者本人或超管**可改展示名（下载时 `Content-Disposition` 的文件名）。不替换文件内容，`slug` 不变。**需携带 token**。

**请求**：

```json
{"raw_filename": "2026年审计报告（修订）.pdf"}
```

**响应** `200`：`DocumentOut`。**失败**：`401` 未登录；`403 无权限操作该文件` 非上传者且非超管；`404` 不存在；`422` 名为空。

### DELETE `/document/{slug}`

仅**上传者本人或超管**可删：DB 记录 + 磁盘文件一并清理（硬删，不可恢复）。**需携带 token**。

**响应** `204` 空。**失败**：`401` 未登录；`403 无权限操作该文件`；`404` 不存在。

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
| is_superuser | bool | 是否超管（默认账号 `ruanfumin` 为 `true`；前端可据此控制管理入口） |

### BaseInfoOut

| 字段 | 类型 | 说明 |
|------|------|------|
| category | CategoryTree[] | 分类树（一级 → 二级） |
| user | UserOut[] | 用户列表 |

### CategoryOut

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| name | string | 分类名称（允许重名） |
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
| is_deleted | bool | 是否在回收站（`false` 才会出现在正常列表；列表接口已按 `is_deleted` 过滤） |
| is_recommended | bool | 是否推荐 |
| create_at | datetime | 发布时间（超管可 PATCH 修改） |
| view_count | int | 阅读量（每次公开详情访问 `GET /articles/{slug}` 自增 +1；**不可** PATCH） |
| like_count | int | 点赞数（通过 `POST /articles/{slug}/like` 自增；**不可** PATCH） |
| user_id | int | 作者用户 id（超管可 PATCH 改归属） |
| categories | CategoryTree[] | 关联分类（二级分类，可为空数组） |
| user | UserOut \| null | 作者，可能为 `null` |

### UploadResult

上传接口（`POST /image/`、`POST /document/`）统一响应：

| 字段 | 类型 | 说明 |
|------|------|------|
| filename | string | 原始文件名 |
| slug | string | 文件标识（含原始扩展名），用于后续 GET / 文章封面 |
| content_type | string | 上传时的 MIME 类型 |
| size_bytes | int | 落盘字节数 |
| url | string | 相对访问地址：图片=预览图，文件=下载地址（前端拼 `BASE`） |
| raw_url | string \| null | 仅图片有值（原图 `?file_type=raw`）；文档为 `null` |

### ImageOut / DocumentOut

两者结构一致：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| slug | string | 文件标识（含原始扩展名） |
| raw_filename | string | 原始文件名 |
| mime_type | string | 上传时的 MIME 类型 |
| size_bytes | int | 原始文件大小（字节） |
| user_id | int | 上传者用户 id（**必填、无默认**，上传接口自动写入当前用户；存量数据已迁移为 1） |
| view | int | 浏览量（每次成功 GET 自增） |
| uploaded_at | datetime | 上传时间 |
| user | UserOut \| null | 上传者 `{id, slug, nickname, is_superuser}`；对应用户不存在时为 null |

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
main.py                  # 入口：挂载路由、CORS、访问日志中间件、lifespan 启动建表
app/
├── routers/             # 路由层：参数校验、404 等 HTTP 状态码
├── service/             # 业务层：校验、分页组装（page_response）
├── dao/                 # 数据层：SQLModel 查询，只 flush 不 commit
├── model/               # 表模型（Category / Article / Image / Document / User）
├── schema/              # 请求 / 响应 Pydantic 模型
├── auth.py              # JWT 签发与校验（get_current_user）
├── errors.py            # ServiceError（业务校验错误）→ 全局 handler 转 400
├── settings.py          # .env 配置、上传目录、MIME 白名单
├── database.py          # 引擎、请求级会话（自动 commit/rollback）、init_db
└── utils/               # WebP 预览图生成、异步文件写入
tests/                   # pytest 用例与 fixtures（conftest.py）
uploads/                 # 上传落盘目录（已 gitignore）
```

---

## 数据库升级（存量库）

启动时的 `create_all` 只建新表、**不会修改已有表结构**。`image` / `document` 的 `user_id` 列迁移**已在部署库执行**（存量数据已置 1）；其他环境（如新搭环境的旧备份库）可用幂等脚本同步：

```bash
uv run python scripts/migrate_add_user_id.py
```

脚本做的事（PG，可重复执行）：

```sql
ALTER TABLE image ADD COLUMN IF NOT EXISTS user_id INTEGER;
UPDATE image SET user_id = 1 WHERE user_id IS NULL;
ALTER TABLE image ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE image ALTER COLUMN user_id DROP DEFAULT;
-- document 同样四条
```

`user_id` 为业务层关联（无数据库外键），**必填、无默认值**——上传接口自动写入当前登录用户 id。

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
- `create_all` 不会修改已有表结构；调整字段后需对存量库手动执行 DDL，或清库重建（本次合并可见性字段时对存量库执行过 `ALTER TABLE article DROP COLUMN is_hidden`）。
- 文章只有 `is_deleted` 一个可见性字段：软删除（`DELETE` → `is_deleted = true`，进回收站），后台 `GET /articles/?is_deleted=true` 找回并用 `POST /articles/{slug}/restore` 恢复；分类为**硬删除**（级联删除子分类并清理关联），分类 `name` 删除后可复用。
- 文章通过 slug 定位，slug 由 UUID 自动生成。
- 文章只能关联二级分类；按 `category_id` 过滤时精确匹配该分类，不聚合子分类。
- 表间关联不使用数据库外键，由业务层维护（`article_category` 关联表）。
- 上传文件落盘 `./uploads/` 目录。
- `requirements.txt` 是给 Docker（pip）用的**钉死版本快照**，由 `uv export --no-dev --no-hashes -o requirements.txt` 生成——改动 `pyproject.toml` 依赖后需重新导出同步，勿手改。
- 项目**无 lint / typecheck / formatter / CI 配置**；包管理与依赖锁以 `pyproject.toml` + `uv.lock` 为准。
