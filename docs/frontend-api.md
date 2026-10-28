# 前端对接文档

> 本文档面向前端开发，覆盖鉴权、错误处理、全部接口与真实响应示例。示例响应均由当前版本 API 实测采集。
>
> 服务端交互契约以本文为准；字段命名与状态码如有疑问，可对照项目 `README.md` 的数据模型章节或在线 ` docs `（FastAPI 自带 `/docs` Swagger 页面，开发环境直接访问）。

---

## 目录

1. [环境与全局约定](#1-环境与全局约定)
2. [鉴权流程](#2-鉴权流程)
3. [统一错误处理](#3-统一错误处理)
4. [分页约定](#4-分页约定)
5. [基础信息 `/base/`](#5-基础信息-base)
6. [分类模块 `/categories`](#6-分类模块-categories)
7. [文章模块 `/articles`](#7-文章模块-articles)
8. [图片模块 `/image`](#8-图片模块-image)
9. [文件模块 `/document`](#9-文件模块-document)
10. [通用数据结构](#10-通用数据结构)
11. [常见问题 FAQ](#11-常见问题-faq)

---

## 1. 环境与全局约定

| 约定 | 说明 |
|------|------|
| 开发地址 | `http://127.0.0.1:8000`（`uv run fastapi dev`） |
| 生产地址 | `http://<host>:8088`（Docker / `python main.py`） |
| 路径尾斜杠 | 集合路径**必须带尾斜杠**：`/articles/`、`/categories/`、`/image/`、`/document/`、`/base/`。不带会返回 `307`，部分客户端对 `307` + POST 请求体处理不一致 |
| 请求编码 | JSON 接口：`Content-Type: application/json`；上传接口：`multipart/form-data`。单文件上传字段名**固定为 `file`**；批量上传字段名**固定为 `files`**（同一字段名重复出现） |
| 时间格式 | `create_at` / `uploaded_at` 为 ISO 8601 **本地时间、无时区后缀**，如 `2026-10-27T13:01:37.520947`，按服务器时区（`Asia/Shanghai`）解析 |
| 跨域 | 前端源必须包含在服务端环境变量 `CORS_ORIGINS`（逗号分隔），否则浏览器拦截 |
| 上传大小 | 服务端强制限制：图片默认 ≤ 10MB（`MAX_IMAGE_SIZE_MB`）、文档默认 ≤ 50MB（`MAX_DOCUMENT_SIZE_MB`）；超限返回 `400`。前端仍建议用 `file.size` 预检，避免白传 |
| 在线调试 | 开发环境访问 `/docs`（Swagger UI）可交互调试全部接口 |

### 鉴权总览

- **角色**：`is_superuser=true` 为**超级管理员**（默认账号 `ruanfumin`），其余均为普通用户。登录后从 `/auth/me` 或 `/base/` 的 `user[].is_superuser` 判断。
- **公开 GET**：文章列表/详情、图片本体 `GET /image/{slug}`、分类、`/base/`。
- **需登录 GET**：图片列表 `GET /image/`、文件列表 `GET /document/`、文件下载 `GET /document/{slug}`。
- **写操作需登录**：分类/文章的 `POST` / `PATCH` / `DELETE`、图片/文件的 `POST` 上传、文件/图片的 `PATCH` / `DELETE`、修改密码；其中**分类管理、批量分类与用户账户管理（`/users`）仅超管**（普通用户 → 403）。
- **权限边界（摘要）**：
  - 文章列表：**匿名** = 公开全量（前台）；**普通用户** = 固定只返回**自己**的文章（`user_id` 参数被忽略）；**超管** = 全量（可按 `user_id` 过滤、`is_deleted=true` 查回收站）。带非法/过期 token → `401`（不降级为匿名）。
  - 文章：普通用户只能改/删/恢复**自己**的；超管可改任意，并可指定 `user_id`（作者）与 `create_at`（发布时间）。`view_count` / `like_count` 对所有人均不可 PATCH。
  - 分类：`GET` 保持公开；**创建/修改/删除分类与批量分类仅超管**，普通用户 → `403 仅超级管理员可管理文章分类`。
  - 用户账户：超管可**创建普通账户**（密码缺省 `abc123`）、**删除普通账户**、**重置普通账户密码为 `abc123`**；超级管理员账户受保护。
  - 图片/文档列表：普通用户只见**自己上传的**；超管见全部。
  - 文档下载：本人或超管；图片本体公开（文章封面依赖）。
  - 文档/图片改名与删除：本人或超管。
- 匿名例外：`POST /articles/{slug}/like`（点赞）无需 token。

---

## 2. 鉴权流程

### 2.1 登录

```http
POST /auth/login
Content-Type: application/json

{"username": "admin", "password": "******"}
```

**成功** `200`：

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxx.xxxxx",
  "token_type": "bearer"
}
```

**失败** `401`：

```json
{"detail": "用户名或密码错误"}
```

> 登录失败（密码错误 / 用户不存在）统一返回该文案，不区分原因。

**前端处理**：把 `access_token` 存入 localStorage（或 pinia / cookie），后续所有写请求带上：

```http
Authorization: Bearer <access_token>
```

```js
// fetch 示例
const res = await fetch(`${BASE}/articles/`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bearer ${localStorage.getItem("token")}`,
  },
  body: JSON.stringify({ title: "新文章" }),
});
```

### 2.2 获取当前用户

```http
GET /auth/me
Authorization: Bearer <token>
```

**成功** `200`：

```json
{
  "id": 1,
  "slug": "5ab74e52a00a",
  "nickname": "管理员"
}
```

> 不返回 `username` 和密码。`id` 与文章/文件的 `user_id` 对应。

**失败**：`401` 未提供认证凭据 / 无效或过期的令牌 / 用户不存在。

### 2.3 修改密码

```http
PUT /auth/password
Authorization: Bearer <token>
Content-Type: application/json

{"old_password": "当前密码", "new_password": "新密码（至少 6 位）"}
```

**成功** `200`：

```json
{"detail": "密码修改成功"}
```

**失败**：

| 状态码 | detail | 场景 |
|--------|--------|------|
| 400 | `原密码错误` | 旧密码不匹配 |
| 401 | `未提供认证凭据` 等 | 未登录 / token 无效 |
| 422 | detail 数组 | `new_password` 不足 6 位或缺字段 |

> 修改成功后，已签发的旧 token 在过期前仍然有效；建议引导用户用新密码重新登录。

### 2.4 前端 401 统一处理建议

```js
// 拦截器伪代码（axios 为例）
if (response.status === 401) {
  localStorage.removeItem("token");
  router.push("/login");
  // 注意：登录接口本身的 401（密码错误）不要跳转，直接展示 detail
}
```

token 过期时间为服务端配置（默认 12 小时），过期后写接口返回 `401 {"detail": "无效或过期的令牌"}`。

### 2.5 用户账户管理（仅超管）

> 仅超级管理员可调用；普通用户 → `403 仅超级管理员可管理用户账户`。无注册接口，普通账户统一由超管创建。

**创建普通账户** `POST /users/`：

```json
{"username": "zhangsan", "nickname": "张三", "password": "abc123"}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | ✓ | 登录名，唯一 |
| nickname | string | ✓ | 展示名，唯一 |
| password | string | ✗ | 至少 6 位；缺省 `abc123` |

成功 `201`：`UserOut`（`{"id", "slug", "nickname", "is_superuser": false}`）。`is_superuser` 不可通过该接口设置。

失败：`400 用户名已存在` / `400 昵称已存在`；`403` 非超管；`422` 字段缺失或密码不足 6 位。

**重置普通账户密码** `POST /users/{id}/reset-password`：

成功 `200`：`{"detail": "密码已重置为 abc123"}`（`DEFAULT_USER_PASSWORD`），重置后旧密码立即失效。

失败：`403 不能重置超级管理员密码`（目标为超管）；`404 用户不存在`；`403` 非超管。

**删除普通账户** `DELETE /users/{id}`：

硬删除账户行，删除后无法登录；已签发的 token 也会因「用户不存在」返回 `401`。

> 该账户已发布的**文章**、已上传的**图片/文档保留**，`user` 关联变为 `null`（无数据库外键）。如需清理内容，请先单独删除再删账户。

成功 `204` 空；失败：`403 不能删除超级管理员账户`（目标为超管）；`404 用户不存在`；`403` 非超管。

---

## 3. 统一错误处理

**所有接口的错误响应都是 JSON**，通过 `detail` 字段给出原因：

| 状态码 | 含义 | detail 类型 |
|--------|------|-------------|
| 400 | 业务校验失败 | **字符串**，可直接 toast |
| 401 | 未认证 / token 无效或过期 | **字符串**（带 `WWW-Authenticate: Bearer` 响应头） |
| 403 | 已登录但无权操作（改他人文章/文件等） | **字符串** |
| 404 | 资源不存在 | **字符串** |
| 422 | 请求参数格式非法 | **数组**，取 `detail[0].msg` 展示 |
| 500 | 服务器内部未预期异常 | **字符串**（固定 `服务器内部错误`） |

**422 响应示例**（创建文章缺 `title`）：

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

**统一解析函数建议**：

```js
function showError(res) {
  const detail = res.detail;
  if (typeof detail === "string") return detail;           // 400/401/404/500
  if (Array.isArray(detail)) return detail[0]?.msg;        // 422
  return "请求失败";
}
```

### 401 的 detail 取值

| detail | 场景 |
|--------|------|
| `未提供认证凭据` | 缺少 `Authorization` 头 |
| `无效或过期的令牌` | token 被篡改或已过期 |
| `用户不存在` | token 合法但对应用户已被删除 |

### 403 的 detail 取值（权限）

| detail | 场景 |
|--------|------|
| `无权指定其他用户发布` | 普通用户创建文章时传他人的 `user_id` |
| `仅超级管理员可管理文章分类` | 普通用户创建/修改/删除分类，或调用批量分类 |
| `仅超级管理员可管理用户账户` | 普通用户创建/删除账户或重置密码 |
| `不能删除超级管理员账户` | DELETE 目标账户是超管 |
| `不能重置超级管理员密码` | 重置密码目标账户是超管 |
| `无权修改他人文章` | PATCH 非自己且非超管的文章 |
| `无权删除他人文章` / `无权恢复他人文章` | DELETE / restore 同上 |
| `无权限操作该文件` | 图片/文档改名或删除非本人且非超管 |
| `无权限查看该文件` | 下载他人文档 |

### 常见 400 业务错误文案

| detail | 触发场景 |
|--------|----------|
| `用户名或密码错误` | 登录失败 |
| `原密码错误` | 修改密码时旧密码不匹配 |
| `父分类不存在` | `parent_id` 指向的分类不存在 |
| `仅支持二级分类，不能创建三级分类` | 在二级分类下再挂子分类 |
| `一级分类不支持调整父级` | PATCH 给一级分类改 `parent_id` |
| `仅支持二级分类，不能调整为一级分类` | PATCH 传 `parent_id=0` |
| `父分类必须是一级分类` | 新父级本身是二级分类 |
| `存在无效的分类` | `category_ids` 含不存在的分类 id |
| `文章仅支持关联二级分类` | `category_ids` 含一级分类 id |
| `字段 title 不能为空` | PATCH 非空字段显式传 `null`（字段名随实际而变） |
| `文章不存在或已删除: xxx` | 批量分类时 slug 不存在（整批不生效） |
| `用户名已存在` / `昵称已存在` | 创建账户时重名 |
| `不支持的图片类型「{实际Content-Type}」，仅支持 JPG、PNG、GIF、WebP、BMP、TIFF、ICO 格式` | 图片 `Content-Type` 不在白名单（`{}` 内为服务端实际收到的 MIME，为空显示 `未知`） |
| `不支持的文件类型「{实际Content-Type}」，仅支持 txt、csv、md、rtf、pdf、doc、docx、docm、xls、xlsx、xlsm、ppt、pptx、pptm、odt、ods、odp、zip、7z、rar、gz、tar、epub 格式` | 文档 `Content-Type` 不在白名单 |
| `图片大小超过限制（最大 10MB）` | 图片超过 `MAX_IMAGE_SIZE_MB` |
| `文件大小超过限制（最大 50MB）` | 文档超过 `MAX_DOCUMENT_SIZE_MB` |
| `文件内容为空` | 上传 0 字节文件 |
| `不是有效的图片文件（内容可能已损坏或格式不符）` | MIME 合法但内容无法被解码（伪图片 / 文件损坏） |
| `服务器磁盘空间已满，请联系管理员清理后重试` | 服务器磁盘写满（`ENOSPC`） |
| `服务器存储目录无写入权限，请联系管理员` | 上传目录无写权限（`EACCES` / `EPERM`） |
| `文件保存到服务器失败，请稍后重试` | 其他落盘 I/O 错误 |
| `图片处理失败，请更换图片后重试` | 生成 WebP 预览图时发生未预期错误 |
| `无权限操作该文件` | PATCH / DELETE 非上传者本人（403） |

### 404 的 detail 取值

`分类不存在`、`文章不存在`、`Image not found`、`Document not found`、`用户不存在`。

---

## 4. 分页约定

所有列表接口统一：

**查询参数**：`page`（默认 1，≥1）、`page_size`（图片/文件默认 30，文章默认 20，范围 1~100）。

**响应结构**：

```json
{
  "data": [],
  "total": 265,
  "page": 1,
  "page_size": 20,
  "has_next": true
}
```

> `page` 超出范围时 `data` 为空数组，不报错。`has_next = page * page_size < total`。

---

## 5. 基础信息 `/base/`

### GET `/base/`

公开。一次拿到导航所需数据：**分类树**（一级 → 二级）+ **用户列表**。分类树按 `sort, id` 升序。

**响应** `200`：

```json
{
  "category": [
    {
      "id": 1,
      "name": "财务信息",
      "sort": 0,
      "children": [
        {
          "id": 2,
          "name": "泵站托管",
          "sort": 0,
          "children": []
        }
      ]
    },
    {
      "id": 3,
      "name": "单位概况",
      "sort": 1,
      "children": []
    }
  ],
  "user": [
    {
      "id": 1,
      "slug": "5ab74e52a00a",
      "nickname": "管理员"
    }
  ]
}
```

> 分类严格二级：一级分类的 `children` 挂二级分类，二级分类 `children` 恒为 `[]`。文章只挂**二级分类**。

---

## 6. 分类模块 `/categories`

> `parent_id=0` 是一级分类（仅展示分组），否则为二级分类（挂文章）。名称**允许重名**。

### GET `/categories/`

公开。扁平列表（一级、二级混在同一数组，按 `parent_id` 自行组树），按 `sort, id` 升序。

**响应** `200`：

```json
[
  {"id": 1, "name": "财务信息", "parent_id": 0, "sort": 0},
  {"id": 2, "name": "泵站托管", "parent_id": 1, "sort": 0},
  {"id": 3, "name": "单位概况", "parent_id": 0, "sort": 1}
]
```

### POST `/categories/`（仅超管）

**请求体**：

```json
{"name": "招标采购", "parent_id": 0, "sort": 2}
```

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| name | string | ✓ | — | 分类名称（允许重名） |
| parent_id | int | ✗ | 0 | `0` = 一级分类；否则必须指向一个一级分类 |
| sort | int | ✗ | 0 | 越小越靠前（同级之间） |

**成功** `201`：

```json
{"id": 4, "name": "招标采购", "parent_id": 0, "sort": 2}
```

**失败**：`403 仅超级管理员可管理文章分类`（普通用户）；`400` 父分类不存在 / 尝试创建三级分类。

### GET `/categories/{id}`（公开）

**成功** `200`：

```json
{"id": 2, "name": "泵站托管", "parent_id": 1, "sort": 0}
```

**失败**：`404 分类不存在`。

### PATCH `/categories/{id}`（仅超管）

只更新传入字段：

```json
{"name": "财务公开", "sort": 10}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | 分类名称 |
| parent_id | int | 二级分类可改挂到另一个一级分类下；一级分类不可调父级、不能传 `0` |
| sort | int | 排序值 |

**成功** `200`：`CategoryOut`。**失败**：`403 仅超级管理员可管理文章分类`（普通用户）；`400` 父级调整非法；`404` 不存在。

### DELETE `/categories/{id}`（仅超管）

硬删除，**级联删除其子分类**，并清理文章的分类关联（文章本体保留）。

**成功** `204` 空 body；**失败** `403 仅超级管理员可管理文章分类`（普通用户）；`404`。

---

## 7. 文章模块 `/articles`

> 文章一律以 **slug** 定位（创建时自动生成的 16 位 hex），**不支持按数字 id 操作**。

### GET `/articles/`

分页列表，按 `id` 倒序（最新创建在前）。

**可见范围**（按调用者身份收敛）：

| 调用者 | 返回范围 |
|--------|----------|
| 匿名（无 `Authorization` 头） | 公开全量（前台列表，行为不变） |
| 普通用户（带 token） | **固定只返回自己**的文章，`user_id` 参数被忽略；`is_deleted=true` 同样只枚举自己的回收站 |
| 超管（带 token） | 全量，`user_id` 过滤与回收站照常使用 |

> 带非法/过期 token → `401`（不静默降级为匿名，避免权限收敛被绕过）。

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| page | int | 1 | 页码 |
| page_size | int | 20 | 每页条数（1~100） |
| category_id | int | 无 | 按**二级分类** id 精确过滤（不聚合一级分类下的子分类） |
| user_id | int | 无 | 按作者过滤（**仅超管生效**；普通用户被强制收敛为本人） |
| is_deleted | bool | false | `false` 正常列表；`true` 回收站（后台用） |

示例：`GET /articles/?page=1&page_size=20&category_id=2`

**响应** `200`（列表**不含 `content`**）：

```json
{
  "data": [
    {
      "id": 1,
      "slug": "bee38b58a04d4e68",
      "cover_img_slug": "0bee5133169c4e888c147aba8864fa14.png",
      "title": "2026年支出预算表公示",
      "is_deleted": false,
      "is_recommended": true,
      "create_at": "2026-10-27T13:01:37.520947",
      "view_count": 0,
      "like_count": 0,
      "categories": [
        {"id": 2, "name": "泵站托管", "sort": 0, "children": []}
      ],
      "user": {
        "id": 1,
        "slug": "5ab74e52a00a",
        "nickname": "管理员"
      }
    }
  ],
  "total": 2,
  "page": 1,
  "page_size": 20,
  "has_next": false
}
```

> 可见性由服务端统一过滤：前台永远拿不到已删文章；后台回收站传 `is_deleted=true`。

### POST `/articles/`（需登录）

**请求体**：

```json
{
  "title": "2026年支出预算表公示",
  "content": "正文内容……",
  "cover_img_slug": "0bee5133169c4e888c147aba8864fa14.png",
  "is_recommended": true,
  "category_ids": [2]
}
```

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| title | string | ✓ | — | 标题 |
| content | string | ✗ | null | 正文（富文本原样存储） |
| cover_img_slug | string | ✗ | null | 封面图 slug（来自 `POST /image/` 返回） |
| is_recommended | bool | ✗ | false | 是否推荐 |
| category_ids | int[] | ✗ | [] | **二级分类** id 列表；含一级分类或不存在的 id → 400 |
| user_id | int | ✗ | 当前登录用户 | **仅超管**：指定发布主体；普通用户传他人 → `403 无权指定其他用户发布` |
| create_at | datetime | ✗ | 服务器当前时间 | **仅超管**：指定发布时间（ISO 8601，如 `2019-12-31T23:59:59`）；普通用户传入被忽略 |

**成功** `201`：`ArticleDetailOut`（比列表多 `content` 字段，结构见 [10. 通用数据结构](#10-通用数据结构)）。

**失败**：`400` 分类无效；`403` 普通用户指定他人为作者；`422` 缺 `title`。

### GET `/articles/{slug}`

公开详情。**每次成功访问 `view_count` +1**（已删文章 `404` 且不计数）。

**响应** `200`：

```json
{
  "id": 1,
  "slug": "bee38b58a04d4e68",
  "cover_img_slug": "0bee5133169c4e888c147aba8864fa14.png",
  "title": "2026年支出预算表公示",
  "content": "正文内容……",
  "is_deleted": false,
  "is_recommended": true,
  "create_at": "2026-10-27T13:01:37.520947",
  "view_count": 1,
  "like_count": 0,
  "user_id": 1,
  "categories": [
    {"id": 2, "name": "泵站托管", "sort": 0, "children": []}
  ],
  "user": {
    "id": 1,
    "slug": "5ab74e52a00a",
    "nickname": "管理员",
    "is_superuser": true
  }
}
```

**失败**：`404 文章不存在`（含已删除）。

> 封面图展示：`<img src="{BASE}/image/{cover_img_slug}">` 默认返回 WebP 预览图；原图加 `?file_type=raw`。

### PATCH `/articles/{slug}`（需登录）

**权限**：作者本人，或超管。他人 → `403 无权修改他人文章`。

只更新传入字段：

```json
{"title": "2026年支出预算表（修订）", "is_recommended": true, "category_ids": [2]}
```

**null 语义**（重要）：

- 可空字段（`content` / `cover_img_slug` / `category_ids`）显式传 `null` 表示**清空**
- 非空字段（`title` / `is_recommended` / `user_id` / `create_at`）传 `null` → `400`
- `category_ids` 传入时**整体替换**关联分类（不是合并）
- 删除/恢复不走 PATCH：见下方 `DELETE` 与 `restore`

**超管专属字段**（普通用户请求中出现会被**忽略**，不影响正文类字段生效）：

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | int | 改发布作者（≥1） |
| create_at | datetime | 改发布时间 |

**对所有人**：`view_count` / `like_count` **不可**通过 PATCH 修改（浏览量走详情访问自增，点赞走 like 接口）。

**成功** `200`：`ArticleDetailOut`。**失败**：`400` / `403` / `404`。

### POST `/articles/{slug}/like`

公开（无需 token），匿名点赞，每次调用 `like_count` +1。可配合 localStorage 限制同一浏览器重复点赞。

**响应** `200`：

```json
{"like_count": 1}
```

**失败**：`404` 文章不存在或已删除。

### DELETE `/articles/{slug}`（需登录）

软删除：移入回收站（`is_deleted = true`），前台列表/详情一律 `404`。

**权限**：作者本人，或超管。他人 → `403 无权删除他人文章`。

**成功** `204` 空 body；**失败** `403` / `404`。

### POST `/articles/{slug}/restore`（需登录）

恢复回收站文章，重新出现在正常列表。对未删除文章调用是**幂等空操作**。

**权限**：作者本人，或超管。他人 → `403 无权恢复他人文章`。

**成功** `200`：`ArticleDetailOut`。**失败**：`401`；`403`；`404`。

### POST `/articles/batch-category`（仅超管）

后台批量把多篇文章**加入**或**移出**一个二级分类。普通用户调用 → `403 仅超级管理员可管理文章分类`（属分类管理操作）。

**请求体**：

```json
{
  "slugs": ["bee38b58a04d4e68", "832b55552c61424f"],
  "category_id": 2,
  "mode": "add"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| slugs | string[] | ✓ | 至少 1 个，服务端去重后处理 |
| category_id | int | ✓ | 目标二级分类 id |
| mode | string | ✓ | `add` 加入 / `remove` 移出 |

**语义**：幂等（`add` 不产生重复关联）；只操作未删除文章；任一 slug 不存在或分类无效 → **整批 400 不生效**。

**成功** `200`（`affected` = 实际处理的文章数）：

```json
{"affected": 1}
```

**失败**：`400` 一级分类 / slug 不存在；`422` slugs 为空或 mode 非法。

### 后台回收站完整流程示例

```js
// 1. 枚举已删文章
const trash = await get("/articles/?is_deleted=true");
// 2. 恢复选中
await post(`/articles/${slug}/restore`);
// 3. 恢复后出现在正常列表
const list = await get("/articles/");
```

---

## 8. 图片模块 `/image`

### POST `/image/`（需登录）

上传图片，`multipart/form-data`，字段名 `file`。服务端自动生成 WebP 预览图（透明背景保留）。

**支持格式**（按 part 的 `Content-Type` 白名单，PIL 均可解码出预览）：

| 扩展名 | MIME |
|--------|------|
| `.jpg` `.jpeg` | `image/jpeg` |
| `.png` | `image/png` |
| `.gif` | `image/gif` |
| `.webp` | `image/webp` |
| `.bmp` | `image/bmp` / `image/x-ms-bmp` |
| `.tif` `.tiff` | `image/tiff` |
| `.ico` | `image/x-icon` / `image/vnd.microsoft.icon` |

> 不在白名单（如 `image/heic`、`image/svg+xml`、`image/avif`）→ `400 不支持的图片类型「…」`。HEIC / AVIF / SVG 需额外解码插件，当前未放开。

**大小限制**：默认 **10MB**（服务端环境变量 `MAX_IMAGE_SIZE_MB` 可调）。超出 → `400 图片大小超过限制（最大 10MB）`；空文件 → `400 文件内容为空`；内容损坏 → `400 不是有效的图片文件（内容可能已损坏或格式不符）`。

**上传失败详情**（均为 `400`，`detail` 为字符串，可直接 toast）：

| detail | 场景 |
|--------|------|
| `不支持的图片类型「…」，仅支持 JPG、PNG、GIF、WebP、BMP、TIFF、ICO 格式` | `Content-Type` 不在白名单（含实际收到的 MIME） |
| `图片大小超过限制（最大 10MB）` | 超过 `MAX_IMAGE_SIZE_MB` |
| `文件内容为空` | 0 字节文件 |
| `不是有效的图片文件（内容可能已损坏或格式不符）` | MIME 合法但 PIL 无法解码 |
| `服务器磁盘空间已满，请联系管理员清理后重试` | 服务器磁盘满（`ENOSPC`） |
| `服务器存储目录无写入权限，请联系管理员` | 上传目录无写权限 |
| `文件保存到服务器失败，请稍后重试` | 其他落盘 I/O 错误 |
| `图片处理失败，请更换图片后重试` | 生成 WebP 预览图时未预期错误 |

> 上述失败均**不会**在磁盘留下半成品、不会写入数据库。

**上传进度（前端）**：图片与文档**共用**同一套进度封装。浏览器原生只有 `XMLHttpRequest.upload.onprogress` 能拿到已发送字节（`fetch` 不行）。服务端为分块流式落盘，不会整文件进内存；进度条反映的是**客户端已发出的字节**，到 100% 后图片还要生成 WebP 预览、文档还要写库，需等 Promise resolve 才算完成。

```js
/**
 * 带进度 + 可取消的上传（图片 / 文档通用）
 * @param {string} url          `${BASE}/image/` 或 `${BASE}/document/`
 * @param {File}   file         <input type="file"> 的 File
 * @param {string} token        JWT
 * @param {object} [opts]
 * @param {(p: {ratio:number, loaded:number, total:number}) => void} [opts.onProgress]
 *        ratio ∈ [0,1]；发送完毕后服务端处理期间不会再来进度事件
 * @param {AbortSignal} [opts.signal] 取消上传（调用 signal.abort()）
 * @returns {Promise<object>}   成功时为 UploadResult JSON
 */
function uploadWithProgress(url, file, token, { onProgress, signal } = {}) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    // 切勿手动 set Content-Type —— multipart boundary 必须由浏览器生成

    xhr.upload.onprogress = (e) => {
      if (onProgress && e.lengthComputable) {
        onProgress({ ratio: e.loaded / e.total, loaded: e.loaded, total: e.total });
      }
    };

    xhr.onload = () => {
      let body = null;
      try {
        body = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        /* 非 JSON 响应忽略 */
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body);
        return;
      }
      const detail = body && body.detail;
      let message = `上传失败（HTTP ${xhr.status}）`;
      if (typeof detail === "string") message = detail;
      else if (Array.isArray(detail) && detail[0]) message = detail[0].msg || message;
      const err = new Error(message);
      err.status = xhr.status;
      err.detail = detail;
      reject(err);
    };
    xhr.onerror = () => reject(new Error("网络错误，上传失败"));
    xhr.onabort = () => {
      const err = new Error("上传已取消");
      err.name = "AbortError";
      reject(err);
    };
    if (signal) {
      if (signal.aborted) {
        xhr.abort();
        return;
      }
      signal.addEventListener("abort", () => xhr.abort(), { once: true });
    }

    const form = new FormData();
    form.append("file", file); // 字段名固定为 file
    xhr.send(form);
  });
}
```

**图片上传示例（含一键取消）**：

```html
<input type="file" id="imgInput" accept="image/jpeg,image/png,image/gif,image/webp,image/bmp,image/tiff" />
<progress id="imgProgress" max="1" value="0" hidden></progress>
<button id="imgCancel" type="button" hidden>取消上传</button>
```

```js
let imgController = null;

async function uploadImageOnce(file, token) {
  // 任何时刻（包括进度未到 100%）都可取消
  imgController = new AbortController();
  cancelBtn.hidden = false;
  progressEl.hidden = false;
  progressEl.value = 0;
  const onAbortClick = () => imgController.abort(); // 一键取消：断开连接，服务端清半成品
  cancelBtn.onclick = onAbortClick;

  try {
    setUiState("uploading");
    const result = await uploadWithProgress(`${BASE}/image/`, file, token, {
      onProgress: ({ ratio }) => (progressEl.value = ratio),
      signal: imgController.signal,
    });
    setUiState("processing"); // 已发完，服务端生成 WebP 预览中
    // result.url / result.raw_url 可直接拼 <img src>
    setUiState("done");
  } catch (err) {
    if (err.name === "AbortError") setUiState("cancelled");
    else showToast(err.message);
  } finally {
    cancelBtn.hidden = true;
    imgController = null;
  }
}
```

**文档上传示例**（同一函数，换 URL）：

```js
const controller = new AbortController();
cancelBtn.onclick = () => controller.abort(); // 进度未到 100% 也可随时取消

try {
  const result = await uploadWithProgress(`${BASE}/document/`, docFile, token, {
    onProgress: ({ ratio, loaded, total }) => {
      progressEl.value = ratio;
      sizeLabel.textContent = `${formatBytes(loaded)} / ${formatBytes(total)}`;
    },
    signal: controller.signal,
  });
  // result.url 为下载地址（需带 Authorization，见文件模块）
} catch (err) {
  if (err.name === "AbortError") console.info("已取消");
  else showToast(err.message);
}
```

> **取消语义**：`xhr.abort()` 会立刻断开 HTTP 连接；服务端 `write_upload_stream` 捕获 `ClientDisconnect` 后删除已写入的半成品，**不会**入库、不会在 `uploads/` 残留。取消在 0%~100% 任意时刻生效。

> 前端选择文件后建议先 `file.size` 与允许上限比对（图片 10MB / 文档 50MB），不合法直接提示，避免白传。

> 浏览器上传时确保 `File.type` 非空（如 `.png` → `image/png`），为空会返回 `400`。

**成功** `200`：

```json
{
  "filename": "photo.png",
  "slug": "0bee5133169c4e888c147aba8864fa14.png",
  "content_type": "image/png",
  "size_bytes": 79,
  "url": "/image/0bee5133169c4e888c147aba8864fa14.png",
  "raw_url": "/image/0bee5133169c4e888c147aba8864fa14.png?file_type=raw"
}
```

| 字段 | 说明 |
|------|------|
| filename | 原始文件名 |
| slug | 文件标识（含扩展名），可用于 `cover_img_slug` |
| content_type | 上传时的 MIME |
| size_bytes | 落盘字节数 |
| url | **预览图**相对地址（拼 BASE 后可直接 `<img src>`） |
| raw_url | **原图**相对地址（`?file_type=raw`） |

> `slug` **保留原始扩展名**，可直接用于文章 `cover_img_slug` 与 `<img src>`。

### POST `/image/batch/`（需登录）

一次提交多张图片（多选上传）。表单字段名为 **`files`**（每个文件一个同名 part）。

**请求**（`multipart/form-data`）：

```
files: <二进制图片 1>
files: <二进制图片 2>
...
```

- 单次最多 **20** 个文件（服务端 `MAX_BATCH_FILES`），超出 → `400 单次最多上传 20 个文件`。
- 先**整批校验类型**，再逐个落盘；单文件大小上限（10MB）、空文件、类型白名单与 `POST /image/` 完全一致。
- **整批原子**：任一文件失败 → `400`，整批不生效——不产生部分图片记录，也不残留磁盘文件。`detail` 会指明第几个文件，如 `第 2 个文件「bad.png」：不是有效的图片文件（内容可能已损坏或格式不符）`。

**成功** `200`：`UploadResult[]`（顺序与请求中 `files` 一致）：

```json
[
  {
    "filename": "a.png",
    "slug": "5894e8c2bc824d0abd7ed539115cb6b9.png",
    "content_type": "image/png",
    "size_bytes": 79,
    "url": "/image/5894e8c2bc824d0abd7ed539115cb6b9.png",
    "raw_url": "/image/5894e8c2bc824d0abd7ed539115cb6b9.png?file_type=raw"
  },
  {
    "filename": "b.png",
    "slug": "6b83f0aa7c1e4aabb9b0c8c4d3f6a111.png",
    "content_type": "image/png",
    "size_bytes": 79,
    "url": "/image/6b83f0aa7c1e4aabb9b0c8c4d3f6a111.png",
    "raw_url": "/image/6b83f0aa7c1e4aabb9b0c8c4d3f6a111.png?file_type=raw"
  }
]
```

**失败**：`400`（逐文件定位原因）/ `401` 未登录 / `422` 未携带任何文件。

> 前端多选：`<input type="file" multiple>` 后逐个 `form.append("files", file)`；进度可用 `uploadWithProgress` 封装（本模块 POST `/image/` 下方），多 part 时反映总上传进度。

**失败**：`400` 见上方失败详情表；`401` 未登录。

### GET `/image/`（需登录）

分页列表，按 `id` 倒序（最新上传在前）。**含上传者信息**。

**可见范围**：超管看到**全部**；普通用户只看到**自己上传的**。

**查询参数**：`page`（默认 1）、`page_size`（默认 30，1~100）。

**响应** `200`：

```json
{
  "data": [
    {
      "id": 1,
      "slug": "0bee5133169c4e888c147aba8864fa14.png",
      "raw_filename": "photo.png",
      "mime_type": "image/png",
      "size_bytes": 79,
      "user_id": 1,
      "view": 0,
      "uploaded_at": "2026-10-27T13:01:37.493067",
      "user": {
        "id": 1,
        "slug": "5ab74e52a00a",
        "nickname": "管理员",
        "is_superuser": true
      }
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 30,
  "has_next": false
}
```

> `user` 为上传者（业务层关联）；对应用户不存在时为 `null`。

**失败**：`401` 未登录。

### GET `/image/{slug}`

**公开**（文章封面等前台场景依赖，不限制上传者）。返回图片文件本体（浏览器可直接打开）。**每次成功访问 `view` +1**。

**查询参数**：`file_type`，默认 `preview`。

| 值 | 说明 |
|----|------|
| `preview` | WebP 预览图（自动压缩，`Content-Type: image/webp`） |
| `raw` | 原图（`Content-Type` 为上传时的 MIME） |

示例：`<img src="{BASE}/image/0bee5133169c4e888c147aba8864fa14.png">`（预览）；`?file_type=raw`（原图）。

**失败**：`404 Image not found`。

### PATCH `/image/{slug}`（需登录）

仅**上传者本人或超管**可改展示名。**不替换文件内容**。

**请求体**：

```json
{"raw_filename": "新图片名.png"}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| raw_filename | string | ✓ | 1~255 字符，空串 422 |

**成功** `200`：`ImageOut`（`raw_filename` 已更新）。**失败**：`401`；`403 无权限操作该文件`；`404`；`422`。

### DELETE `/image/{slug}`（需登录）

仅**上传者本人或超管**可删：同时清理 **DB 记录 + 原图 + WebP 预览图**，不可恢复。

**成功** `204` 空 body。**失败**：`401`；`403`；`404`（已删再删也是 404）。

---

## 9. 文件模块 `/document`

### POST `/document/`（需登录）

上传文档，字段名 `file`（按 `Content-Type` 白名单校验）。

**支持格式**：

| 类别 | 扩展名 | MIME |
|------|--------|------|
| 文本/数据 | `.txt` | `text/plain` |
| | `.csv` | `text/csv` / `application/csv` |
| | `.md` | `text/markdown` |
| | `.rtf` | `application/rtf` / `text/rtf` |
| PDF | `.pdf` | `application/pdf` |
| Word | `.doc` | `application/msword` |
| | `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| | `.docm` | `application/vnd.ms-word.document.macroEnabled.12` |
| Excel | `.xls` | `application/vnd.ms-excel` |
| | `.xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| | `.xlsm` | `application/vnd.ms-excel.sheet.macroEnabled.12` |
| PPT | `.ppt` | `application/vnd.ms-powerpoint` |
| | `.pptx` | `application/vnd.openxmlformats-officedocument.presentationml.presentation` |
| | `.pptm` | `application/vnd.ms-powerpoint.presentation.macroEnabled.12` |
| OpenDocument | `.odt` `.ods` `.odp` | `application/vnd.oasis.opendocument.*` |
| 压缩包 | `.zip` | `application/zip` / `application/x-zip-compressed` |
| | `.7z` | `application/x-7z-compressed` |
| | `.rar` | `application/vnd.rar` / `application/x-rar-compressed` |
| | `.gz` `.tgz` | `application/gzip` / `application/x-gzip` |
| | `.tar` | `application/x-tar` |
| 电子书 | `.epub` | `application/epub+zip` |

**大小限制**：默认 **50MB**（服务端环境变量 `MAX_DOCUMENT_SIZE_MB` 可调）。超出 → `400 文件大小超过限制（最大 50MB）`；空文件 → `400 文件内容为空`。

**上传失败详情**（均为 `400`，`detail` 为字符串，可直接 toast）：

| detail | 场景 |
|--------|------|
| `不支持的文件类型「…」，仅支持 txt、csv、md、rtf、pdf、doc、docx、docm、xls、xlsx、xlsm、ppt、pptx、pptm、odt、ods、odp、zip、7z、rar、gz、tar、epub 格式` | `Content-Type` 不在白名单（含实际收到的 MIME，为空显示 `未知`） |
| `文件大小超过限制（最大 50MB）` | 超过 `MAX_DOCUMENT_SIZE_MB` |
| `文件内容为空` | 0 字节文件 |
| `服务器磁盘空间已满，请联系管理员清理后重试` | 服务器磁盘满（`ENOSPC`） |
| `服务器存储目录无写入权限，请联系管理员` | 上传目录无写权限（`EACCES` / `EPERM`） |
| `文件保存到服务器失败，请稍后重试` | 其他落盘 I/O 错误 |

> 上述失败均**不会**在磁盘留下半成品、不会写入数据库。

**上传进度**：与图片完全同一套封装——把 URL 换成 `${BASE}/document/` 即可，支持进度条与 `AbortController` 取消（完整 `uploadWithProgress` 见 [8. 图片模块](#8-图片模块-image)）。

```js
const result = await uploadWithProgress(`${BASE}/document/`, file, token, {
  onProgress: ({ ratio }) => (progressEl.value = ratio),
  signal: abortController.signal,
});
// result.url 为下载地址（下载需带 Authorization，见下方 GET /document/{slug}）
```

**成功** `200`：

```json
{
  "filename": "报告.pdf",
  "slug": "ed9134a751e34f0fa50e5f879b92c647.pdf",
  "content_type": "application/pdf",
  "size_bytes": 8,
  "url": "/document/ed9134a751e34f0fa50e5f879b92c647.pdf",
  "raw_url": null
}
```

| 字段 | 说明 |
|------|------|
| filename | 原始文件名 |
| slug | 文件标识（含扩展名） |
| content_type | 上传时的 MIME |
| size_bytes | 落盘字节数 |
| url | **下载**相对地址（拼 BASE 后 `window.open` 或 fetch 转 blob） |
| raw_url | 固定 `null`（文档无预览/原图之分） |

### POST `/document/batch/`（需登录）

一次提交多个文件。表单字段名为 **`files`**（每个文件一个同名 part）。

**请求**（`multipart/form-data`）：

```
files: <二进制文件 1>
files: <二进制文件 2>
...
```

- 单次最多 **20** 个文件（服务端 `MAX_BATCH_FILES`），超出 → `400 单次最多上传 20 个文件`。
- 先**整批校验类型**，再逐个落盘；单文件大小上限（50MB）、空文件、类型白名单与 `POST /document/` 完全一致。
- **整批原子**：任一文件失败 → `400`，整批不生效——不产生部分记录，也不残留磁盘文件。`detail` 指明第几个文件，如 `第 2 个文件「empty.txt」：文件内容为空`。

**成功** `200`：`UploadResult[]`（`raw_url` 恒为 `null`，顺序与请求一致）：

```json
[
  {
    "filename": "a.txt",
    "slug": "ed9134a751e34f0fa50e5f879b92c647.txt",
    "content_type": "text/plain",
    "size_bytes": 5,
    "url": "/document/ed9134a751e34f0fa50e5f879b92c647.txt",
    "raw_url": null
  }
]
```

**失败**：`400`（逐文件定位原因）/ `401` 未登录 / `422` 未携带任何文件。

**失败**：`400` 见上方失败详情表；`401` 未登录。

### GET `/document/`（需登录）

分页列表，**含上传者信息**。默认按**上传时间倒序**（最新在前）。

**可见范围**：超管看到**全部**；普通用户只看到**自己上传的**。

**查询参数**：`page`（默认 1）、`page_size`（默认 30，1~100），另支持 `sort`（均倒序，非法值 422）：

| 值 | 含义 |
|----|------|
| `uploaded_at`（默认） | 上传时间倒序 |
| `view` | 浏览量倒序（最热在前） |

示例：`GET /document/?sort=view&page=1&page_size=30`

**响应** `200`：

```json
{
  "data": [
    {
      "id": 1,
      "slug": "ed9134a751e34f0fa50e5f879b92c647.pdf",
      "raw_filename": "报告.pdf",
      "mime_type": "application/pdf",
      "size_bytes": 8,
      "user_id": 1,
      "view": 0,
      "uploaded_at": "2026-10-27T13:01:37.511184",
      "user": {
        "id": 1,
        "slug": "5ab74e52a00a",
        "nickname": "管理员",
        "is_superuser": true
      }
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 30,
  "has_next": false
}
```

**失败**：`401` 未登录。

### GET `/document/{slug}`（需登录）

下载文件（带原始文件名）。**每次成功访问 `view` +1**。

**权限**：上传者本人或超管。他人 → `403 无权限查看该文件`。

**响应**：文件二进制流，`Content-Disposition: attachment`，`Content-Type` 为上传时的 MIME。

前端下载示例：

```js
// 需带 Authorization 头；window.open 无法带自定义头时用 fetch 转 blob
const res = await fetch(`${BASE}/document/${slug}`, {
  headers: { Authorization: `Bearer ${token}` },
});
const blob = await res.blob();
// 触发下载…
```

**失败**：`401`；`403 无权限查看该文件`；`404 Document not found`。

### PATCH `/document/{slug}`（需登录）

仅**上传者本人或超管**可改文档展示名（下载时 `Content-Disposition` 的文件名）。**不替换文件内容**，`slug` / `size_bytes` / `uploaded_at` 不变。

**请求体**：

```json
{"raw_filename": "2026年审计报告（修订）.pdf"}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| raw_filename | string | ✓ | 新展示名，1~255 字符，空串 422 |

**成功** `200`：`DocumentOut`（`raw_filename` 已更新）。

**失败**：

| 状态码 | detail | 场景 |
|--------|--------|------|
| 401 | `未提供认证凭据` 等 | 未登录 / token 无效 |
| 403 | `无权限操作该文件` | 已登录但不是上传者且非超管 |
| 404 | `Document not found` | slug 不存在 |
| 422 | detail 数组 | `raw_filename` 为空或超长 |

### DELETE `/document/{slug}`（需登录）

仅**上传者本人或超管**可删：同时清理 **DB 记录与磁盘文件**，不可恢复。删除后 `GET /document/{slug}` 与列表均不再返回。

**成功** `204` 空 body。

**失败**：

| 状态码 | detail | 场景 |
|--------|--------|------|
| 401 | `未提供认证凭据` 等 | 未登录 / token 无效 |
| 403 | `无权限操作该文件` | 已登录但不是上传者且非超管 |
| 404 | `Document not found` | slug 不存在（已删再删也是 404） |

```js
// 前端删除示例
async function deleteDocument(slug) {
  const res = await fetch(`${BASE}/document/${slug}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (res.status === 204) return true;
  // 403 → 提示无权限；404 → 已被删除，刷新列表即可
  throw new Error(await parseDetail(res));
}
```

---

## 10. 通用数据结构

### TokenOut

| 字段 | 类型 | 说明 |
|------|------|------|
| access_token | string | JWT，放 `Authorization: Bearer <此处>` |
| token_type | string | 固定 `"bearer"` |

### UserOut

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| slug | string | URL 唯一标识 |
| nickname | string | 展示名 |
| is_superuser | bool | 是否超级管理员（默认账号 `ruanfumin` 为 `true`） |

> 不返回 `username` / 密码。前端可用 `is_superuser` 控制管理入口显隐。

### CategoryOut

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| name | string | 名称（允许重名） |
| parent_id | int | `0` = 一级分类，否则为二级分类 |
| sort | int | 越小越靠前 |

### CategoryTree

`CategoryOut` 去掉 `parent_id`，增加 `children: CategoryTree[]`（二级恒为 `[]`）。

### ArticleOut（列表） / ArticleDetailOut（详情）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| slug | string | 操作文章的唯一键 |
| cover_img_slug | string \| null | 封面图 slug → `GET /image/{slug}` |
| title | string | 标题 |
| content | string \| null | 正文（**仅详情/创建/修改响应有**，列表没有） |
| is_deleted | bool | 是否在回收站 |
| is_recommended | bool | 是否推荐 |
| create_at | datetime | 发布时间（超管可 PATCH 修改） |
| view_count | int | 阅读量（详情访问 +1，**不可** PATCH） |
| like_count | int | 点赞数（like 接口 +1，**不可** PATCH） |
| user_id | int | 作者用户 id（超管可 PATCH 改归属） |
| categories | CategoryTree[] | 关联的二级分类 |
| user | UserOut \| null | 作者 |

### UploadResult

上传接口（`POST /image/`、`POST /document/`）统一响应：

| 字段 | 类型 | 说明 |
|------|------|------|
| filename | string | 原始文件名 |
| slug | string | 文件标识（含扩展名） |
| content_type | string | 上传时的 MIME |
| size_bytes | int | 落盘字节数 |
| url | string | 相对访问地址：图片=预览图，文件=下载地址（前端拼 `BASE`） |
| raw_url | string \| null | 仅图片有值（原图 `?file_type=raw`）；文档为 `null` |

> 批量上传接口 `POST /image/batch/`、`POST /document/batch/` 返回 **`UploadResult[]`**（顺序与请求中 `files` 一致）。

### ImageOut / DocumentOut（结构一致）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| slug | string | 文件标识（含扩展名） |
| raw_filename | string | 原始文件名 |
| mime_type | string | MIME 类型 |
| size_bytes | int | 原始文件大小（字节） |
| user_id | int | 上传者用户 id（对应 `/base/` 用户列表的 `id`） |
| view | int | 浏览量 |
| uploaded_at | datetime | 上传时间 |
| user | UserOut \| null | 上传者；用户不存在时为 `null` |

### PageResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| data | T[] | 当前页数据 |
| total | int | 总记录数 |
| page | int | 当前页码 |
| page_size | int | 每页条数 |
| has_next | bool | 是否有下一页 |

---

## 11. 常见问题 FAQ

**Q：请求 `/articles`（不带尾斜杠）返回 307？**
集合路径必须带尾斜杠：`/articles/`。307 会重定向，部分浏览器对重定向后的 POST/PATCH 请求体处理异常。

**Q：上传图片返回 400「不支持的图片类型「…」」？**
检查文件 part 的 `Content-Type`（`detail` 里「」内即服务端实际收到的值）。某些场景（如手动拼 multipart、旧浏览器）`File.type` 为空，会被判为非法。前端务必用 `FormData.append("file", fileObj)` 让浏览器自动填类型。

**Q：上传进度条一直不动 / 拿不到进度？**
`fetch` 无法读取上传字节进度，必须用 `XMLHttpRequest` 的 `upload.onprogress`（见 [8. 图片模块](#8-图片模块-image) 的 `uploadWithProgress`，图片/文档通用）。注意：
1. 进度只反映**客户端已发送**字节；
2. 发送到 100% 后服务端还要落盘 / 生成 WebP 预览图，需等 Promise resolve 才算完成（可加「处理中」态）；
3. 不要手动设置 `Content-Type: multipart/form-data`，否则丢失 boundary，服务端会 422；
4. 需要取消时用 `AbortController`，服务端会清理半成品。

**Q：上传大文件报 400「文件大小超过限制」？**
图片默认上限 10MB、文档 50MB（服务端 `MAX_IMAGE_SIZE_MB` / `MAX_DOCUMENT_SIZE_MB` 可调）。前端应在选择文件时先用 `file.size` 预检，给出友好提示，避免白传。

**Q：上传报 400「服务器磁盘空间已满」/「无写入权限」/「保存到服务器失败」？**
这是**服务端存储问题**，不是用户文件的问题。前端直接 toast `detail` 即可；磁盘满与权限问题需运维介入（清理 `uploads/` 或修目录权限），用户侧重试通常无效。

**Q：浏览器控制台报 CORS 错误？**
前端源（如 `http://localhost:5173`）必须加入服务端 `.env` 的 `CORS_ORIGINS`（逗号分隔多个），改完需重启服务。

**Q：写接口全部 401？**
确认请求头带了 `Authorization: Bearer <token>`，且 token 未过期（默认 12 小时）。401 后清 token 跳登录。

**Q：文章详情 404 但列表里明明有？**
确认用的是 `slug` 而不是数字 `id`。数字 id 不会解析为文章，一律 404。

**Q：`category_ids` 传了一级分类 id 报 400？**
文章只能挂**二级分类**。先用 `/base/` 的树或 `/categories/` 的扁平列表挑出二级分类（`parent_id != 0`）的 id。

**Q：PATCH 文章传 `"content": null` 是清空还是忽略？**
显式传 `null` = 清空；不传该字段 = 保持不变（服务端按 `exclude_unset` 处理）。

**Q：文章按分类筛选时，选一级分类查不到文章？**
`category_id` 过滤只匹配二级分类的精确关联，不聚合其子分类。前端需把一级分类展开为其子分类 id 集合再查询。

**Q：`user` 字段什么时候是 null？**
文件/文章记录的 `user_id` 对应的用户已被删除时为 `null`（无数据库外键，仅业务关联）。`user_id` 必填无默认，上传接口自动写入当前登录用户；存量历史数据已迁移为 1。

**Q：时间字段解析偏差？**
`create_at` / `uploaded_at` 无时区后缀，是服务器本地时间（`Asia/Shanghai`）。JS 侧 `new Date("2026-10-27T13:01:37.520947")` 按浏览器本地时区解析，跨时区部署时注意。

---

## 附：典型对接流程（发布一篇带封面的文章）

```js
// 1. 登录
const { access_token } = await post("/auth/login", { username, password });
localStorage.setItem("token", access_token);

// 2. 拿分类树，选二级分类 id
const { category } = await get("/base/");

// 3. 上传封面图（需要进度条时改用 uploadWithProgress，见图片模块）
const form = new FormData();
form.append("file", coverFile);
const cover = await postForm("/image/", form);
// cover.url 即预览图相对地址，cover.slug 用于文章封面

// 4. 创建文章（user_id 可选：不传归属当前登录用户，传则指定发布主体）
const article = await post("/articles/", {
  title,
  content,
  cover_img_slug: cover.slug,
  is_recommended: false,
  category_ids: [二级分类id],
  // user_id: 1,
});

// 5. 列表展示封面
// <img src={`${BASE}/image/${item.cover_img_slug}`} />  // WebP 预览图
```

其中 `get/post` 为统一封装：自动带 token、统一解析 `detail` 错误、401 跳登录。

